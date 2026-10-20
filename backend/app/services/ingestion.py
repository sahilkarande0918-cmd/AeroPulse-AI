"""CSV/JSON adapters for fragmented maintenance data: sensors, technical records, parts, work orders.

Guarantees: schema + units validation, timestamp normalisation to UTC, idempotent re-imports
(file hash + record natural keys), duplicate detection, conflicts rejected (never merged),
row-level rejection report, provenance (batch id + source name + mapping version).
"""
import csv
import hashlib
import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Aircraft, Engine, IngestionBatch, MaintenanceRecord, Part, SensorReading, WorkOrder
from app.services import fleet

MAPPING = json.loads((Path(__file__).resolve().parents[1] / "mappings" / "mapping_v1.json").read_text())
SOURCE_TYPES = tuple(MAPPING["sources"])
MAX_REPORTED = 200
_HEADER_UNIT = re.compile(r"^\s*(?P<name>[A-Za-z0-9_]+)\s*\[(?P<unit>[^\]]+)\]\s*$")


class SchemaError(ValueError):
    pass


def parse_ts(value, tz: str = MAPPING["default_timezone"]) -> datetime:
    s = str(value).strip()
    if not s:
        raise ValueError("empty timestamp")
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(tz))
    return dt.astimezone(UTC)


def _canonical_unit(u: str) -> str | None:
    for canon, aliases in MAPPING["unit_aliases"].items():
        if u.strip().lower() in {a.lower() for a in aliases}:
            return canon
    return None


def _records(filename: str, content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig")
    if filename.lower().endswith(".json"):
        data = json.loads(text)
        data = data.get("records", data) if isinstance(data, dict) else data
        if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
            raise SchemaError("JSON must be a list of objects or {\"records\": [...]}")
        return [{str(k): v for k, v in r.items()} for r in data]
    return list(csv.DictReader(io.StringIO(text)))


def _resolve_columns(source: str, columns: list[str]) -> tuple[dict, dict, list[str]]:
    """Return ({canonical: column}, {sensor: (column, factor, offset)}, notes)."""
    spec = MAPPING["sources"][source]
    lower = {c.strip().lower(): c for c in columns}
    colmap = {}
    for canon, aliases in spec["aliases"].items():
        for a in aliases:
            if a.lower() in lower:
                colmap[canon] = lower[a.lower()]
                break
    missing = [r for r in spec["required"] if r not in colmap]
    if missing:
        raise SchemaError(f"missing required columns: {', '.join(missing)} (mapping {MAPPING['version']})")
    sensors, notes = {}, []
    if source == "sensor":
        for c in columns:
            m = _HEADER_UNIT.match(c)
            name, unit = (m["name"].lower(), m["unit"]) if m else (c.strip().lower(), None)
            if name not in MAPPING["sensor_units"]:
                continue
            expected = MAPPING["sensor_units"][name]
            scale, offset = 1.0, 0.0
            if unit is not None:
                canon = _canonical_unit(unit)
                if canon is None:
                    raise SchemaError(f"column '{c}': unknown unit '{unit}'")
                if canon != expected:
                    conv = MAPPING["conversions"].get(f"{canon}->{expected}")
                    if not conv:
                        raise SchemaError(f"column '{c}': unit {canon} incompatible with expected {expected}")
                    scale, offset = conv["scale"], conv["offset"]
                    notes.append(f"{name}: converted {canon} -> {expected}")
            sensors[name] = (c, scale, offset)
        if not sensors:
            raise SchemaError("no sensor columns (s1..s21) found")
    return colmap, sensors, notes


def ingest(db: Session, source: str, filename: str, content: bytes, source_name: str, user_id: int | None) -> tuple[IngestionBatch, bool]:
    """Returns (batch, already_imported)."""
    if source not in SOURCE_TYPES:
        raise SchemaError(f"unknown source type '{source}'")
    digest = hashlib.sha256(source.encode() + b"\0" + source_name.encode() + b"\0" + content).hexdigest()
    prior = db.scalar(select(IngestionBatch).where(IngestionBatch.content_hash == digest)
                      .order_by(IngestionBatch.id.desc()))
    if prior and not prior.report.get("schema_errors"):
        return prior, True
    batch = IngestionBatch(user_id=user_id, source_type=source, source_name=source_name, filename=filename[:255],
                           mapping_version=MAPPING["version"], content_hash=digest, report={})
    db.add(batch)
    db.flush()
    report = {"schema_errors": [], "rejected_rows": [], "conflicts": [], "notes": [], "mapping_version": MAPPING["version"]}
    try:
        rows = _records(filename, content)
        if not rows:
            raise SchemaError("file contains no records")
        colmap, sensors, notes = _resolve_columns(source, list(rows[0].keys()))
        report["notes"] += notes
        counts = HANDLERS[source](db, batch, rows, colmap, sensors, report)
    except (SchemaError, UnicodeDecodeError, json.JSONDecodeError, csv.Error) as e:
        report["schema_errors"].append(str(e))
        counts = {"rejected": 0}
    for k, v in counts.items():
        setattr(batch, k, v)
    report["rejected_rows"] = report["rejected_rows"][:MAX_REPORTED]
    report["conflicts"] = report["conflicts"][:MAX_REPORTED]
    batch.report = report
    db.flush()
    return batch, False


def _get(row, colmap, key, default=None):
    col = colmap.get(key)
    v = row.get(col) if col else None
    return default if v is None or (isinstance(v, str) and not v.strip()) else v


def _sensor(db, batch, rows, colmap, sensors, report):
    engines = {e.serial: e for e in db.scalars(select(Engine))}
    c = {"accepted": 0, "duplicates": 0, "conflicts": 0, "rejected": 0}
    seen: dict[tuple, tuple] = {}
    touched = set()
    for i, row in enumerate(rows, start=2):
        try:
            serial = str(_get(row, colmap, "engine_serial", "")).strip()
            eng = engines.get(serial)
            if eng is None:
                raise ValueError(f"unknown engine serial '{serial}' (register assets before ingesting data)")
            cycle = int(str(_get(row, colmap, "cycle")).strip())
            if cycle < 1:
                raise ValueError("cycle must be >= 1")
            ts = parse_ts(_get(row, colmap, "recorded_at", ""))
            values = {}
            for s, (col, scale, offset) in sensors.items():
                raw = row.get(col)
                if raw is None or str(raw).strip() == "":
                    continue  # missing value: kept missing; TrustTwin flags it downstream
                values[s] = round(float(raw) * scale + offset, 6)
        except (ValueError, TypeError) as e:
            c["rejected"] += 1
            report["rejected_rows"].append({"row": i, "reason": str(e)})
            continue
        key, payload = (eng.id, cycle), (ts.isoformat(), values)
        existing = seen.get(key)
        if existing is None:
            r = db.scalar(select(SensorReading).where(SensorReading.engine_id == eng.id, SensorReading.cycle == cycle))
            existing = (r.recorded_at.isoformat(), r.values) if r else None
        if existing is not None:
            if existing == payload:
                c["duplicates"] += 1
            else:
                c["conflicts"] += 1
                report["conflicts"].append({"row": i, "key": f"{serial}/cycle {cycle}",
                                            "reason": "differs from an existing record for the same engine and cycle; not merged"})
            continue
        seen[key] = payload
        db.add(SensorReading(engine_id=eng.id, cycle=cycle, recorded_at=ts, values=values, batch_id=batch.id))
        c["accepted"] += 1
        touched.add(eng.id)
    db.flush()
    for eid in sorted(touched):
        fleet.refresh_engine(db, db.get(Engine, eid))
    report["notes"].append(f"Predictions refreshed for {len(touched)} engine(s).")
    return c


def _maintenance(db, batch, rows, colmap, sensors, report):
    aircraft = {a.tail: a for a in db.scalars(select(Aircraft))}
    engines = {e.serial: e for e in db.scalars(select(Engine))}
    types = MAPPING["sources"]["maintenance"]["record_types"]
    c = {"accepted": 0, "duplicates": 0, "conflicts": 0, "rejected": 0}
    for i, row in enumerate(rows, start=2):
        try:
            rid = str(_get(row, colmap, "source_record_id", "")).strip()
            ac = aircraft.get(str(_get(row, colmap, "aircraft_tail", "")).strip())
            if not rid or ac is None:
                raise ValueError("missing record id or unknown aircraft tail")
            es = _get(row, colmap, "engine_serial")
            eng = engines.get(str(es).strip()) if es else None
            if es and (eng is None or eng.aircraft_id != ac.id):
                raise ValueError(f"engine '{es}' unknown or not fitted to {ac.tail}")
            rtype = str(_get(row, colmap, "record_type", "")).strip().lower()
            if rtype not in types:
                raise ValueError(f"record_type must be one of {types}")
            rec = dict(aircraft_id=ac.id, engine_id=eng.id if eng else None,
                       performed_at=parse_ts(_get(row, colmap, "performed_at", "")), record_type=rtype,
                       description=str(_get(row, colmap, "description", ""))[:2000],
                       performed_by=str(_get(row, colmap, "performed_by", "unspecified"))[:64])
        except (ValueError, TypeError) as e:
            c["rejected"] += 1
            report["rejected_rows"].append({"row": i, "reason": str(e)})
            continue
        old = db.scalar(select(MaintenanceRecord).where(MaintenanceRecord.source_system == batch.source_name,
                                                        MaintenanceRecord.source_record_id == rid))
        if old:
            same = all(getattr(old, k) == v for k, v in rec.items())
            c["duplicates" if same else "conflicts"] += 1
            if not same:
                report["conflicts"].append({"row": i, "key": rid, "reason": "record id reused with different content; not merged"})
            continue
        db.add(MaintenanceRecord(**rec, source_system=batch.source_name, source_record_id=rid, batch_id=batch.id))
        db.flush()
        c["accepted"] += 1
    return c


def _parts(db, batch, rows, colmap, sensors, report):
    c = {"accepted": 0, "updated": 0, "duplicates": 0, "conflicts": 0, "rejected": 0}
    for i, row in enumerate(rows, start=2):
        try:
            pn = str(_get(row, colmap, "part_number", "")).strip().upper()
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9\-_.]{1,63}", pn):
                raise ValueError("invalid part number")
            qty = {k: int(_get(row, colmap, k, d)) for k, d in
                   (("on_hand", None), ("reorder_threshold", None), ("replenishment_qty", 0), ("lead_time_days", 14))}
            if min(qty.values()) < 0:
                raise ValueError("quantities must be >= 0")
            vals: dict = {"name": str(_get(row, colmap, "name", "")).strip()[:128], "unit": str(_get(row, colmap, "unit", "ea"))[:16], **qty}
            eta = _get(row, colmap, "replenishment_eta")
            vals["replenishment_eta"] = parse_ts(eta) if eta else None
        except (ValueError, TypeError) as e:
            c["rejected"] += 1
            report["rejected_rows"].append({"row": i, "reason": str(e)})
            continue
        old = db.scalar(select(Part).where(Part.part_number == pn))
        if old is None:
            db.add(Part(part_number=pn, **vals, batch_id=batch.id))
            db.flush()
            c["accepted"] += 1
        elif (old.name, old.unit) != (vals["name"], vals["unit"]):
            c["conflicts"] += 1
            report["conflicts"].append({"row": i, "key": pn, "reason": f"identity mismatch: existing '{old.name}' ({old.unit}); not merged"})
        elif all(getattr(old, k) == v for k, v in vals.items()):
            c["duplicates"] += 1
        else:
            for k, v in vals.items():
                setattr(old, k, v)
            old.batch_id = batch.id
            c["updated"] += 1
    return c


def _work_orders(db, batch, rows, colmap, sensors, report):
    spec = MAPPING["sources"]["work_orders"]
    aircraft = {a.tail: a for a in db.scalars(select(Aircraft))}
    engines = {e.serial: e for e in db.scalars(select(Engine))}
    c = {"accepted": 0, "duplicates": 0, "conflicts": 0, "rejected": 0}
    ext_to_code = {w.external_id: w.code for w in db.scalars(select(WorkOrder).where(WorkOrder.source == batch.source_name))}
    for i, row in enumerate(rows, start=2):
        try:
            ext = str(_get(row, colmap, "external_id", "")).strip()
            ac = aircraft.get(str(_get(row, colmap, "aircraft_tail", "")).strip())
            if not ext or ac is None:
                raise ValueError("missing external id or unknown aircraft tail")
            es = _get(row, colmap, "engine_serial")
            eng = engines.get(str(es).strip()) if es else None
            if es and (eng is None or eng.aircraft_id != ac.id):
                raise ValueError(f"engine '{es}' unknown or not fitted to {ac.tail}")
            ttype, skill = str(_get(row, colmap, "task_type", "")).lower(), str(_get(row, colmap, "required_skill", "")).lower()
            if ttype not in spec["task_types"] or skill not in spec["skills"]:
                raise ValueError(f"task_type must be in {spec['task_types']} and skill in {spec['skills']}")
            dur, prio = int(_get(row, colmap, "duration_hours")), int(_get(row, colmap, "priority"))
            if not 1 <= dur <= 12 or not 1 <= prio <= 4:
                raise ValueError("duration_hours must be 1-12 and priority 1-4")
            parts_raw = _get(row, colmap, "parts", [])
            if isinstance(parts_raw, str):
                parts_raw = [{"part_number": p.split(":")[0].strip().upper(), "qty": int(p.split(":")[1])}
                             for p in parts_raw.split(";") if p.strip()]
            parts = [{"part_number": str(p["part_number"]).upper(), "qty": int(p["qty"])} for p in parts_raw]
            preds_raw = _get(row, colmap, "predecessors", [])
            preds_raw = [p.strip() for p in preds_raw.split(";") if p.strip()] if isinstance(preds_raw, str) else list(preds_raw)
            unknown = [p for p in preds_raw if p not in ext_to_code]
            if unknown:
                raise ValueError(f"unknown predecessor(s) {unknown}; list predecessors earlier in the file")
            rec = dict(aircraft_id=ac.id, engine_id=eng.id if eng else None, title=str(_get(row, colmap, "title"))[:160],
                       task_type=ttype, required_skill=skill, duration_hours=dur, priority=prio,
                       due_at=parse_ts(_get(row, colmap, "due_at", "")), parts=parts,
                       predecessor_codes=[ext_to_code[p] for p in preds_raw])
        except (ValueError, TypeError, KeyError, IndexError) as e:
            c["rejected"] += 1
            report["rejected_rows"].append({"row": i, "reason": str(e)})
            continue
        old = db.scalar(select(WorkOrder).where(WorkOrder.source == batch.source_name, WorkOrder.external_id == ext))
        if old:
            same = all(getattr(old, k) == v for k, v in rec.items())
            c["duplicates" if same else "conflicts"] += 1
            if not same:
                report["conflicts"].append({"row": i, "key": ext, "reason": "external id reused with different content; not merged"})
            continue
        wo = WorkOrder(code=fleet.next_wo_code(db), **rec, source=batch.source_name, external_id=ext,
                       approval_state="pending", batch_id=batch.id)
        db.add(wo)
        db.flush()
        ext_to_code[ext] = wo.code
        c["accepted"] += 1
    return c


HANDLERS = {"sensor": _sensor, "maintenance": _maintenance, "parts": _parts, "work_orders": _work_orders}
