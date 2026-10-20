"""Persistence model. Prediction, Recommendation and Decision are deliberately separate entities.

Relationships load with lazy="selectin" (one batched query per relationship, not one per row):
against a remote database such as Neon every extra round trip costs hundreds of milliseconds.
"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime, utcnow


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    full_name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32))  # admin | officer | technician | analyst
    password_hash: Mapped[str] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Aircraft(Base):
    __tablename__ = "aircraft"
    id: Mapped[int] = mapped_column(primary_key=True)
    tail: Mapped[str] = mapped_column(String(32), unique=True)
    type_name: Mapped[str] = mapped_column(String(128))
    base: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="available")
    engines: Mapped[list["Engine"]] = relationship(back_populates="aircraft", order_by="Engine.position", lazy="selectin")


class Engine(Base):
    __tablename__ = "engines"
    id: Mapped[int] = mapped_column(primary_key=True)
    serial: Mapped[str] = mapped_column(String(32), unique=True)
    aircraft_id: Mapped[int] = mapped_column(ForeignKey("aircraft.id"))
    position: Mapped[int] = mapped_column(Integer)
    source_dataset: Mapped[str] = mapped_column(String(64))       # provenance of the sensor stream
    source_unit: Mapped[int | None] = mapped_column(Integer)      # C-MAPSS unit id it replays
    aircraft: Mapped[Aircraft] = relationship(back_populates="engines", lazy="selectin")


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (UniqueConstraint("engine_id", "cycle"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    engine_id: Mapped[int] = mapped_column(ForeignKey("engines.id"), index=True)
    cycle: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime)
    values: Mapped[dict] = mapped_column(JSON)                    # {"s2": 642.1, ...}; missing keys = missing
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_batches.id"))


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    engine_id: Mapped[int] = mapped_column(ForeignKey("engines.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    cycle: Mapped[int] = mapped_column(Integer)
    model_version: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16))                # VALID | DEGRADED | UNAVAILABLE
    rul: Mapped[float | None] = mapped_column(Float)
    rul_lower: Mapped[float | None] = mapped_column(Float)
    rul_upper: Mapped[float | None] = mapped_column(Float)
    quality: Mapped[dict] = mapped_column(JSON)
    evidence: Mapped[list] = mapped_column(JSON)
    scenario_run_id: Mapped[int | None] = mapped_column(ForeignKey("scenario_runs.id"))


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"))
    aircraft_id: Mapped[int] = mapped_column(ForeignKey("aircraft.id"))
    engine_id: Mapped[int] = mapped_column(ForeignKey("engines.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    action: Mapped[str] = mapped_column(String(128))
    priority: Mapped[int] = mapped_column(Integer)                # 1 critical .. 4 routine
    rationale: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="proposed")  # proposed|approved|rejected|info_requested
    work_order_id: Mapped[int | None] = mapped_column(ForeignKey("work_orders.id"))
    scenario_run_id: Mapped[int | None] = mapped_column(ForeignKey("scenario_runs.id"))


class Decision(Base):
    """Human decision on a recommendation or schedule. Never created by the model."""
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_type: Mapped[str] = mapped_column(String(24))          # recommendation | schedule
    target_id: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(24))             # approve | reject | request_inspection | request_data
    reason: Mapped[str] = mapped_column(Text)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    user: Mapped[User] = relationship(lazy="selectin")


class Technician(Base):
    __tablename__ = "technicians"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    skills: Mapped[list] = mapped_column(JSON)
    shift_start_hour: Mapped[int] = mapped_column(Integer)
    shift_end_hour: Mapped[int] = mapped_column(Integer)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    unavailable: Mapped[list] = mapped_column(JSON, default=list)  # [{"start": iso, "end": iso, "reason": str}]


class Part(Base):
    __tablename__ = "parts"
    id: Mapped[int] = mapped_column(primary_key=True)
    part_number: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    unit: Mapped[str] = mapped_column(String(16), default="ea")
    on_hand: Mapped[int] = mapped_column(Integer)
    reorder_threshold: Mapped[int] = mapped_column(Integer)
    replenishment_qty: Mapped[int] = mapped_column(Integer, default=0)
    replenishment_eta: Mapped[datetime | None] = mapped_column(UTCDateTime)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=14)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_batches.id"))


class WorkOrder(Base):
    __tablename__ = "work_orders"
    __table_args__ = (UniqueConstraint("source", "external_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    aircraft_id: Mapped[int] = mapped_column(ForeignKey("aircraft.id"))
    engine_id: Mapped[int | None] = mapped_column(ForeignKey("engines.id"))
    title: Mapped[str] = mapped_column(String(160))
    task_type: Mapped[str] = mapped_column(String(32))            # inspection | replacement | servicing | troubleshooting
    required_skill: Mapped[str] = mapped_column(String(32))
    duration_hours: Mapped[int] = mapped_column(Integer)
    priority: Mapped[int] = mapped_column(Integer)
    due_at: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(24), default="open")  # open|scheduled|in_progress|done|cancelled
    approval_state: Mapped[str] = mapped_column(String(24), default="pending")  # pending|approved|rejected
    predecessor_codes: Mapped[list] = mapped_column(JSON, default=list)
    parts: Mapped[list] = mapped_column(JSON, default=list)       # [{"part_number": str, "qty": int}]
    planned_start: Mapped[datetime | None] = mapped_column(UTCDateTime)
    assigned_technician: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(32), default="synthetic")
    external_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_batches.id"))
    aircraft: Mapped[Aircraft] = relationship(lazy="selectin")


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"
    __table_args__ = (UniqueConstraint("source_system", "source_record_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    aircraft_id: Mapped[int] = mapped_column(ForeignKey("aircraft.id"), index=True)
    engine_id: Mapped[int | None] = mapped_column(ForeignKey("engines.id"))
    performed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    record_type: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    performed_by: Mapped[str] = mapped_column(String(64))
    source_system: Mapped[str] = mapped_column(String(64))
    source_record_id: Mapped[str] = mapped_column(String(64))
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_batches.id"))


class Schedule(Base):
    __tablename__ = "schedules"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    solver: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), default="proposed")  # proposed|approved|rejected|superseded
    horizon_start: Mapped[datetime] = mapped_column(UTCDateTime)
    input_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON)
    scenario_run_id: Mapped[int | None] = mapped_column(ForeignKey("scenario_runs.id"))


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))                 # trusttwin | policy_comparison
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    seed: Mapped[int] = mapped_column(Integer)
    params: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    result_hash: Mapped[str] = mapped_column(String(64))


class IngestionBatch(Base):
    __tablename__ = "ingestion_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    source_type: Mapped[str] = mapped_column(String(32))          # sensor | maintenance | parts | work_orders
    source_name: Mapped[str] = mapped_column(String(64))
    filename: Mapped[str] = mapped_column(String(255))
    mapping_version: Mapped[str] = mapped_column(String(32))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    accepted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    conflicts: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    report: Mapped[dict] = mapped_column(JSON)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class AuditEvent(Base):
    """Append-only at the application layer; hash-chained so tampering is detectable (not prevented)."""
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
