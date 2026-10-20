"""Constrained maintenance planning: OR-Tools CP-SAT optimiser + rule-based baseline.

Time unit: whole hours from horizon start. Hard constraints (never relaxed):
  * each scheduled task gets exactly one technician holding the required skill
  * a technician does one task at a time and only inside shifts / outside leave
  * one task at a time per aircraft (bay/access conflict)
  * precedence: successor starts after predecessor ends; successor dropped if predecessor is
  * spare parts: cumulative consumption never exceeds stock on hand + arrivals so far
  * task starts no earlier than its release (e.g. pending approval lead time)
Tasks that cannot be placed are reported as unscheduled with a diagnosed reason.
Objective (configurable weights): priority-weighted lateness + unscheduled penalty + completion time.
"""
import copy
import hashlib
import json
from collections import OrderedDict
from dataclasses import asdict, dataclass, field

from ortools.sat.python import cp_model

PRIORITY_WEIGHT = {1: 8, 2: 4, 3: 2, 4: 1}
DEFAULT_WEIGHTS = {"lateness": 10, "unscheduled": 2000, "completion": 1}


@dataclass
class Task:
    id: str
    aircraft: str
    skill: str
    duration: int
    priority: int
    due: int
    release: int = 0
    parts: dict[str, int] = field(default_factory=dict)
    predecessors: list[str] = field(default_factory=list)
    title: str = ""


@dataclass
class Tech:
    id: str
    skills: list[str]
    blocked: list[tuple[int, int]]  # [start, end) intervals unavailable (off-shift, leave)


@dataclass
class PartStock:
    on_hand: int
    arrivals: list[tuple[int, int]] = field(default_factory=list)  # (hour, qty)


@dataclass
class Problem:
    horizon: int
    tasks: list[Task]
    techs: list[Tech]
    parts: dict[str, PartStock]
    weights: dict = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))


def merge(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Union of [start, end) intervals; fixed intervals in a NoOverlap must not overlap each other."""
    out: list[list[int]] = []
    for a, b in sorted(i for i in intervals if i[1] > i[0]):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def _part_available_by(stock: PartStock, qty: int, horizon: int) -> int | None:
    """Earliest hour at which cumulative supply reaches qty (ignoring competition)."""
    level = stock.on_hand
    if level >= qty:
        return 0
    for t, q in sorted(stock.arrivals):
        level += q
        if level >= qty and t < horizon:
            return t
    return None


def diagnose(p: Problem) -> dict[str, str]:
    """Static reasons a task can never be placed, independent of the optimiser."""
    reasons: dict[str, str] = {}
    by_id = {t.id: t for t in p.tasks}
    for t in p.tasks:
        qualified = [x for x in p.techs if t.skill in x.skills]
        if not qualified:
            reasons[t.id] = f"No available technician holds skill '{t.skill}'."
            continue
        if not any(_earliest_free(x.blocked, t.release, t.duration, p.horizon) is not None for x in qualified):
            reasons[t.id] = f"No qualified technician has a free {t.duration} h window within the horizon."
            continue
        for pn, q in t.parts.items():
            stock = p.parts.get(pn)
            when = _part_available_by(stock, q, p.horizon) if stock else None
            if when is None:
                have = (stock.on_hand + sum(a for _, a in stock.arrivals)) if stock else 0
                reasons[t.id] = f"Part {pn}: need {q}, only {have} on hand or due within horizon."
                break
            if when + t.duration > p.horizon:
                reasons[t.id] = f"Part {pn} arrives at +{when} h, too late to finish within horizon."
                break
        for d in t.predecessors:
            if d not in by_id:
                reasons.setdefault(t.id, f"Predecessor {d} is not in the work queue.")
    changed = True
    while changed:  # propagate through precedence chains
        changed = False
        for t in p.tasks:
            if t.id not in reasons and any(d in reasons for d in t.predecessors):
                reasons[t.id] = f"Blocked by unschedulable predecessor {next(d for d in t.predecessors if d in reasons)}."
                changed = True
    return reasons


def _earliest_free(busy: list[tuple[int, int]], start: int, dur: int, horizon: int) -> int | None:
    t = start
    for b0, b1 in sorted(busy):
        if b1 <= t:
            continue
        if b0 >= t + dur:
            break
        t = max(t, b1)
    return t if t + dur <= horizon else None


def problem_hash(p: Problem) -> str:
    return hashlib.sha256(json.dumps(asdict(p), sort_keys=True, default=str).encode()).hexdigest()


_PLANS: OrderedDict[str, dict] = OrderedDict()   # CP-SAT is deterministic here, so identical inputs reuse the plan


def solve_cpsat(p: Problem, deterministic_limit: float = 10.0) -> dict:
    key = f"{problem_hash(p)}:{deterministic_limit}"
    if key not in _PLANS:
        _PLANS[key] = _solve_cpsat(p, deterministic_limit)
        if len(_PLANS) > 64:
            _PLANS.popitem(last=False)
    return copy.deepcopy(_PLANS[key])


def _solve_cpsat(p: Problem, deterministic_limit: float) -> dict:
    static = diagnose(p)
    w = {**DEFAULT_WEIGHTS, **p.weights}
    m = cp_model.CpModel()
    H = p.horizon
    start, end, present, assign = {}, {}, {}, {}
    tech_intervals: dict[str, list] = {x.id: [] for x in p.techs}
    aircraft_intervals: dict[str, list] = {}
    for t in p.tasks:
        pres = m.new_bool_var(f"p_{t.id}")
        if t.id in static:
            m.add(pres == 0)
        s = m.new_int_var(t.release, H, f"s_{t.id}")
        e = m.new_int_var(t.release, H, f"e_{t.id}")
        m.add(e == s + t.duration)
        iv = m.new_optional_interval_var(s, t.duration, e, pres, f"i_{t.id}")
        aircraft_intervals.setdefault(t.aircraft, []).append(iv)
        start[t.id], end[t.id], present[t.id] = s, e, pres
        lits = []
        for x in p.techs:
            if t.skill not in x.skills:
                continue
            lit = m.new_bool_var(f"a_{t.id}_{x.id}")
            tech_intervals[x.id].append(m.new_optional_interval_var(s, t.duration, e, lit, f"ti_{t.id}_{x.id}"))
            assign[t.id, x.id] = lit
            lits.append(lit)
        m.add(sum(lits) == pres)
    for x in p.techs:
        fixed = [m.new_interval_var(b0, b1 - b0, b1, f"blk_{x.id}_{k}") for k, (b0, b1) in enumerate(merge(x.blocked))]
        m.add_no_overlap(tech_intervals[x.id] + fixed)
    for ivs in aircraft_intervals.values():
        m.add_no_overlap(ivs)
    for t in p.tasks:
        for d in t.predecessors:
            if d in present:
                m.add(start[t.id] >= end[d]).only_enforce_if(present[t.id])
                m.add_implication(present[t.id], present[d])
    for pn, stock in p.parts.items():
        users = [t for t in p.tasks if pn in t.parts]
        if not users:
            continue
        times: list = [0]
        deltas, actives = [stock.on_hand], [m.new_constant(1)]
        for at, q in stock.arrivals:
            times.append(at); deltas.append(q); actives.append(m.new_constant(1))
        for t in users:
            times.append(start[t.id]); deltas.append(-t.parts[pn]); actives.append(present[t.id])
        m.add_reservoir_constraint_with_active(times, deltas, actives, 0, 10**6)

    late = {}
    for t in p.tasks:
        late[t.id] = m.new_int_var(0, H, f"late_{t.id}")
        m.add(late[t.id] >= end[t.id] - t.due)
    m.minimize(sum(PRIORITY_WEIGHT[t.priority] * (w["lateness"] * late[t.id]
                                                   + w["unscheduled"] * (1 - present[t.id])
                                                   + w["completion"] * end[t.id]) for t in p.tasks))
    solver = cp_model.CpSolver()
    # Deterministic-time limit: the same plan on a fast laptop and on a throttled 0.1-CPU host.
    solver.parameters.max_deterministic_time = deterministic_limit
    solver.parameters.max_time_in_seconds = 60   # wall-clock safety net only
    solver.parameters.num_workers = 1          # deterministic results for reproducible scenarios
    solver.parameters.random_seed = 7
    status = solver.solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"solver": "cp-sat", "status": solver.status_name(status), "assignments": [],
                "unscheduled": [{"task": t.id, "reason": static.get(t.id, "Solver returned no solution.")} for t in p.tasks]}
    assignments, unscheduled = [], []
    for t in p.tasks:
        if not solver.value(present[t.id]):
            reason = static.get(t.id) or "Insufficient technician/aircraft capacity in horizon at acceptable cost."
            unscheduled.append({"task": t.id, "reason": reason})
            continue
        tech = next(x.id for x in p.techs if (t.id, x.id) in assign and solver.value(assign[t.id, x.id]))
        assignments.append({"task": t.id, "technician": tech, "start": solver.value(start[t.id]),
                            "end": solver.value(end[t.id])})
    out = {"solver": "cp-sat", "status": solver.status_name(status),
           "assignments": assignments, "unscheduled": unscheduled}
    return _finalise(p, out)


def solve_greedy(p: Problem) -> dict:
    """Rule-based baseline: earliest-due-date list scheduling, earliest finishing qualified technician."""
    static = diagnose(p)
    busy = {x.id: list(x.blocked) for x in p.techs}
    ac_busy: dict[str, list] = {}
    consumed: dict[str, list[tuple[int, int]]] = {pn: [] for pn in p.parts}
    done: dict[str, int] = {}
    assignments, unscheduled = [], []
    pending = sorted(p.tasks, key=lambda t: (t.priority, t.due, t.id))
    for _ in range(len(pending) + 1):  # repeat passes so predecessors get placed first
        progress = False
        for t in list(pending):
            if t.id in static:
                unscheduled.append({"task": t.id, "reason": static[t.id]}); pending.remove(t); continue
            if any(d not in done for d in t.predecessors):
                continue
            pending.remove(t); progress = True
            ready = max([t.release, *[done[d] for d in t.predecessors]])
            best = None
            for x in p.techs:
                if t.skill not in x.skills:
                    continue
                s: int | None = ready
                while s is not None:
                    s = _earliest_free(busy[x.id] + ac_busy.get(t.aircraft, []), s, t.duration, p.horizon)
                    if s is None:
                        break
                    if all(_stock_ok(p.parts[pn], consumed[pn] + [(s, q)]) for pn, q in t.parts.items()):
                        break
                    s += 1
                if s is not None and (best is None or s < best[0]):
                    best = (s, x.id)
            if best is None:
                unscheduled.append({"task": t.id, "reason": "No feasible slot found by greedy rule."})
                continue
            s, xid = best
            busy[xid].append((s, s + t.duration))
            ac_busy.setdefault(t.aircraft, []).append((s, s + t.duration))
            for pn, q in t.parts.items():
                consumed[pn].append((s, q))
            done[t.id] = s + t.duration
            assignments.append({"task": t.id, "technician": xid, "start": s, "end": s + t.duration})
        if not progress:
            break
    for t in pending:
        unscheduled.append({"task": t.id, "reason": "Blocked by unscheduled predecessor."})
    return _finalise(p, {"solver": "greedy-edd", "status": "HEURISTIC",
                         "assignments": assignments, "unscheduled": unscheduled})


def _stock_ok(stock: PartStock, consumed: list[tuple[int, int]]) -> bool:
    """Stock level never negative; arrivals at an hour count before consumption at that hour."""
    events = sorted([(0, stock.on_hand), *stock.arrivals, *[(t, -c) for t, c in consumed]],
                    key=lambda e: (e[0], -e[1]))
    level = 0
    for _, d in events:
        level += d
        if level < 0:
            return False
    return True


def verify(p: Problem, result: dict) -> list[str]:
    """Independent hard-constraint check. Returns violations (empty list = valid plan)."""
    v = []
    by = {t.id: t for t in p.tasks}
    techs = {x.id: x for x in p.techs}
    placed = {a["task"]: a for a in result["assignments"]}
    for a in result["assignments"]:
        t, x = by[a["task"]], techs[a["technician"]]
        if t.skill not in x.skills:
            v.append(f"{t.id}: technician {x.id} lacks skill {t.skill}")
        if a["end"] - a["start"] != t.duration or a["start"] < t.release or a["end"] > p.horizon:
            v.append(f"{t.id}: bad timing")
        for b0, b1 in x.blocked:
            if a["start"] < b1 and b0 < a["end"]:
                v.append(f"{t.id}: overlaps unavailability of {x.id}")
        for d in t.predecessors:
            if d not in placed or placed[d]["end"] > a["start"]:
                v.append(f"{t.id}: precedence on {d} violated")
    for key in ("technician", "aircraft"):
        groups: dict[str, list] = {}
        for a in result["assignments"]:
            groups.setdefault(a["technician"] if key == "technician" else by[a["task"]].aircraft, []).append(a)
        for g, items in groups.items():
            items.sort(key=lambda a: a["start"])
            for i, j in zip(items, items[1:]):
                if j["start"] < i["end"]:
                    v.append(f"{key} {g}: {i['task']} overlaps {j['task']}")
    for pn, stock in p.parts.items():
        cons = [(placed[t.id]["start"], t.parts[pn]) for t in p.tasks if pn in t.parts and t.id in placed]
        if not _stock_ok(stock, cons):
            v.append(f"part {pn}: consumption exceeds supply")
    return v


def score(p: Problem, result: dict) -> float:
    """Objective evaluated identically for every solver so plans are comparable."""
    w = {**DEFAULT_WEIGHTS, **p.weights}
    by = {t.id: t for t in p.tasks}
    total = sum(PRIORITY_WEIGHT[by[a["task"]].priority] * (w["lateness"] * max(0, a["end"] - by[a["task"]].due)
                                                           + w["completion"] * a["end"]) for a in result["assignments"])
    total += sum(PRIORITY_WEIGHT[by[u["task"]].priority] * w["unscheduled"] for u in result["unscheduled"])
    return float(total)


def _part_ready(p: Problem, placed: dict, task: Task, pn: str, q: int, upto: int) -> int:
    """Earliest hour the part could be drawn given every other placed task's consumption."""
    by = {t.id: t for t in p.tasks}
    others = [(a["start"], by[k].parts[pn]) for k, a in placed.items() if k != task.id and pn in by[k].parts]
    for t in range(upto + 1):
        if _stock_ok(p.parts[pn], others + [(t, q)]):
            return t
    return upto


def _finalise(p: Problem, out: dict) -> dict:
    """Attach per-task explanations and verify hard constraints before anything is returned."""
    by = {t.id: t for t in p.tasks}
    placed = {a["task"]: a for a in out["assignments"]}
    for a in out["assignments"]:
        t = by[a["task"]]
        why = []
        part_ready = max([_part_ready(p, placed, t, pn, q, a["start"]) for pn, q in t.parts.items()] or [0])
        pred_ready = max([placed[d]["end"] for d in t.predecessors if d in placed] or [0])
        floor = max(t.release, part_ready, pred_ready)
        if t.release and t.release == floor:
            why.append(f"not before +{t.release} h (release/approval lead time)")
        if part_ready and part_ready == floor:
            why.append(f"waits for spare parts ({', '.join(t.parts)}) available at +{part_ready} h")
        if pred_ready and pred_ready == floor:
            why.append(f"after predecessor tasks finish at +{pred_ready} h")
        if a["start"] > floor:
            why.append(f"{a['start'] - floor} h later than earliest possible: technician shift/capacity or aircraft access")
        late = max(0, a["end"] - t.due)
        a.update(aircraft=t.aircraft, title=t.title, priority=t.priority, due=t.due, late_hours=late,
                 explanation="; ".join(why) or "scheduled at earliest feasible time")
    out["objective"] = score(p, out)
    out["violations"] = verify(p, out)
    if out["violations"]:
        raise AssertionError(f"planner produced an infeasible plan: {out['violations']}")
    out["kpis"] = {
        "scheduled": len(out["assignments"]), "unscheduled": len(out["unscheduled"]),
        "late_tasks": sum(1 for a in out["assignments"] if a["late_hours"] > 0),
        "total_late_hours": sum(a["late_hours"] for a in out["assignments"]),
        "makespan_h": max([a["end"] for a in out["assignments"]] or [0]),
    }
    out["problem"] = {"horizon": p.horizon, "tasks": [asdict(t) for t in p.tasks],
                      "techs": [asdict(x) for x in p.techs],
                      "parts": {k: asdict(s) for k, s in p.parts.items()}}
    return out
