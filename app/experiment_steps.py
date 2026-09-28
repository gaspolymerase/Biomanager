"""What is done to an experiment's mice, planned and recorded.

An experiment's plan is a list of manipulations (ExperimentStep): what
(Tamoxifen, HDM), the dose (20 mg/kg, 25 µg), the route, which treatment
group (blank: every mouse), and the days: "1", "2-5", "1, 8, 15". Day 1 is
the experiment's start date, so each day has a date once it has one.

Each day of each manipulation is recorded when it is done
(ExperimentStepRecord): the date, by whom, which mice got it, and for a
dose per body weight the amount each mouse got, worked out from its latest
weight (and the volume, given the solution's concentration). A body-weight
step ("weigh") records the weights themselves, into the same MouseWeight
series the experiment's body-weight table shows.

The same plan, records and weights are what a notebook page shows in its
"Colony experiment" block (frontend/src/blocks/experiment.js), live or
frozen at a moment; "Add to notebook" on the experiment makes a notebook
page with that block in it. Due days are on the calendar, with the colony's
dates.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, g, jsonify, redirect, request, url_for
from sqlalchemy import select

from . import access, lab
from .db import SessionLocal
from .models import Experiment, ExperimentMouse, ExperimentStep, ExperimentStepRecord, MouseRecord, MouseWeight

bp = Blueprint("expsteps", __name__, url_prefix="/colony/experiments")

KINDS = {
    "injection": ("Injection", "syringe"),
    "challenge": ("Challenge", "virus"),
    "treatment": ("Treatment", "droplet"),
    "surgery": ("Surgery", "stethoscope"),
    "behavior": ("Behaviour", "gauge"),
    "sample": ("Sample", "vial"),
    "imaging": ("Imaging", "microscope"),
    "weigh": ("Body weight", "scale"),
    "other": ("Other", "note"),
}
MAX_DAY = 1000
MAX_DAYS_PER_STEP = 400
NOTEBOOK_PAGE_KEY = "experiment_notebook_page:{experiment}:{user}"


@bp.before_request
def require_login():
    if g.get("user") is None:
        return redirect(url_for("login", next=request.path))
    return None


# ---------------------------------------------------------------- days

_RANGE = re.compile(r"^(-?\d+)\s*(?:-|–|—|~|to|\.\.)\s*(-?\d+)$")


def parse_days(text: str) -> list[int]:
    """"1" → [1]; "2-5" and "2/3/4/5" → [2, 3, 4, 5]; "1, 8, 15" → [1, 8,
    15]; "d1-3, d7" too. ValueError with a sentence to show otherwise."""
    raw = (text or "").strip().lower().replace("days", "").replace("day", "")
    if not raw:
        raise ValueError("Say on which days, e.g. 1, or 2-5, or 1, 8, 15.")
    out: set[int] = set()
    for part in re.split(r"[,;/&]|\band\b|\s{2,}", raw):
        part = part.strip().lstrip("d").strip()
        if not part:
            continue
        match = _RANGE.match(part.replace(" d", " ").replace("-d", "-"))
        if match:
            first, last = int(match.group(1)), int(match.group(2))
            if last < first:
                first, last = last, first
            if last - first > MAX_DAYS_PER_STEP:
                raise ValueError(f"Day {first} to {last} is too long a stretch for one line.")
            out.update(range(first, last + 1))
        elif re.fullmatch(r"-?\d+", part):
            out.add(int(part))
        else:
            # "2 3 4 5": single spaces between numbers
            bits = part.split()
            if bits and all(re.fullmatch(r"-?\d+", b) for b in bits):
                out.update(int(b) for b in bits)
            else:
                raise ValueError(f"“{part}” isn't a day or a range of days (like 2-5).")
    if any(abs(d) > MAX_DAY for d in out):
        raise ValueError(f"Days go up to {MAX_DAY}.")
    if len(out) > MAX_DAYS_PER_STEP:
        raise ValueError("That is more days than one line can hold.")
    return sorted(out)


def days_label(days: list[int]) -> str:
    """[2, 3, 4, 5, 9] → "2–5, 9"."""
    runs, out = [], []
    for d in days:
        if runs and d == runs[-1][1] + 1:
            runs[-1][1] = d
        else:
            runs.append([d, d])
    for first, last in runs:
        out.append(str(first) if first == last else f"{first}–{last}")
    return ", ".join(out)


def day_date(start: date | None, day: int) -> date | None:
    """Day 1 is the start date."""
    return start + timedelta(days=day - 1) if start else None


def safe_days(step: ExperimentStep) -> list[int]:
    try:
        return parse_days(step.days)
    except ValueError:
        return []


# ---------------------------------------------------------------- doses

_MASS = {"kg": 1e6, "g": 1e3, "mg": 1.0, "µg": 1e-3, "ug": 1e-3, "mcg": 1e-3, "ng": 1e-6, "pg": 1e-9}
_VOLUME = {"l": 1e6, "ml": 1e3, "µl": 1.0, "ul": 1.0, "nl": 1e-3}
_UNITS = {"iu": "IU", "u": "U", "mmol": "mmol", "µmol": "µmol", "umol": "µmol", "nmol": "nmol"}
_QTY = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*([a-zµμ]+)\s*(?:/\s*([a-zµμ]+))?\s*$", re.I)


def _unit(u: str) -> str:
    return (u or "").lower().replace("μ", "µ")


def parse_quantity(text: str):
    """"20 mg/kg" → (20.0, "mg", "kg"); "25 µg" → (25.0, "µg", None);
    None when it isn't a number and a unit."""
    m = _QTY.match(text or "")
    if not m:
        return None
    return float(m.group(1).replace(",", ".")), _unit(m.group(2)), (_unit(m.group(3)) if m.group(3) else None)


def fmt_mass(mg: float) -> str:
    if mg >= 1000:
        return f"{mg / 1000:.3g} g"
    if mg >= 0.1:
        return f"{mg:.3g} mg"
    if mg >= 1e-4:
        return f"{mg * 1000:.3g} µg"
    return f"{mg * 1e6:.3g} ng"


def fmt_volume(ul: float) -> str:
    return f"{ul / 1000:.3g} mL" if ul >= 1000 else f"{ul:.3g} µL"


def dose_for(dose: str, concentration: str, grams: float | None) -> dict:
    """What one mouse gets: {"amount": "0.48 mg", "volume": "48 µL"}, or
    {"needs": "a weight"} when a per-weight dose has no weight to use.
    A dose that isn't a number and unit is shown as it is."""
    q = parse_quantity(dose)
    if q is None:
        return {"amount": dose.strip()} if (dose or "").strip() else {}
    value, unit, per = q
    body = None
    if per in ("kg", "g"):
        if grams is None:
            return {"needs": "a weight"}
        body = grams / 1000 if per == "kg" else grams
        value *= body
    out: dict = {}
    if unit in _MASS:
        mg = value * _MASS[unit]
        out["amount"] = fmt_mass(mg)
        c = parse_quantity(concentration)
        if c and c[1] in _MASS and c[2] in _VOLUME and c[0] > 0:
            ul = mg / (c[0] * _MASS[c[1]] / _VOLUME[c[2]])
            out["volume"] = fmt_volume(ul)
    elif unit in _VOLUME:
        out["volume"] = fmt_volume(value * _VOLUME[unit])
    elif unit in _UNITS:
        out["amount"] = f"{value:.3g} {_UNITS[unit]}"
        c = parse_quantity(concentration)
        if c and _UNITS.get(c[1]) == _UNITS[unit] and c[2] in _VOLUME and c[0] > 0:
            out["volume"] = fmt_volume(value / (c[0] / _VOLUME[c[2]]))
    else:
        out["amount"] = f"{value:.3g} {unit}" + ("" if body is not None else "")
    return out


def per_weight(dose: str) -> bool:
    q = parse_quantity(dose)
    return bool(q and q[2] in ("kg", "g"))


# ---------------------------------------------------------------- reading

def _load(session, experiment_id: int) -> Experiment:
    exp = session.get(Experiment, experiment_id)
    if exp is None:
        abort(404)
    return exp


def _members(exp: Experiment, group: str = "") -> list[ExperimentMouse]:
    group = (group or "").strip().lower()
    rows = [em for em in exp.memberships if em.mouse is not None]
    if group:
        rows = [em for em in rows if (em.treatment_group or "").strip().lower() == group]
    return sorted(rows, key=lambda em: em.mouse.mouse_id or 0)


def weights_by_mouse(session, mouse_ids: list[int]) -> dict[int, list[MouseWeight]]:
    out: dict[int, list[MouseWeight]] = {m: [] for m in mouse_ids}
    if not mouse_ids:
        return out
    for w in session.scalars(select(MouseWeight).where(MouseWeight.mouse_id_fk.in_(mouse_ids))
                             .order_by(MouseWeight.weigh_date)):
        out[w.mouse_id_fk].append(w)
    return out


def weight_on(weights: list[MouseWeight], day: date | None) -> MouseWeight | None:
    """The latest weight on or before `day` (the latest of all without one)."""
    usable = [w for w in weights if day is None or w.weigh_date <= day]
    return usable[-1] if usable else None


def _record_dict(r: ExperimentStepRecord) -> dict:
    try:
        mice = json.loads(r.mice or "[]")
    except ValueError:
        mice = []
    return {"id": r.id, "done_on": r.done_on.isoformat(), "done_by": r.done_by, "note": r.note,
            "mice": mice, "count": len(mice)}


def step_dict(step: ExperimentStep) -> dict:
    label, icon = KINDS.get(step.kind, KINDS["other"])
    return {"id": step.id, "days": step.days, "days_label": days_label(safe_days(step)) or step.days,
            "kind": step.kind, "kind_label": label, "icon": icon, "agent": step.agent, "dose": step.dose,
            "route": step.route, "concentration": step.concentration, "group": step.treatment_group,
            "notes": step.notes, "per_weight": per_weight(step.dose)}


def step_title(step: ExperimentStep) -> str:
    what = step.agent or KINDS.get(step.kind, KINDS["other"])[0]
    return " ".join(filter(None, [what, step.dose, step.route]))


def schedule(exp: Experiment, today: date | None = None) -> list[dict]:
    """Every day of every manipulation, in order: its date, and whether it
    is done, due today, overdue or to come."""
    today = today or date.today()
    rows = []
    for step in exp.steps:
        done = {r.day: r for r in step.records}
        group_size = len(_members(exp, step.treatment_group))
        for day in safe_days(step):
            when = day_date(exp.start_date, day)
            record = done.get(day)
            if record is not None:
                state = "done"
            elif when is None:
                state = "planned"
            elif when < today:
                state = "overdue"
            elif when == today:
                state = "today"
            else:
                state = "upcoming"
            rows.append({"step_id": step.id, "day": day, "date": when.isoformat() if when else "",
                         "title": step_title(step), "kind": step.kind, "icon": step_dict(step)["icon"],
                         "group": step.treatment_group, "group_size": group_size, "state": state,
                         "record": _record_dict(record) if record else None})
    rows.sort(key=lambda r: (r["day"], r["step_id"]))
    return rows


def page_data(session, exp: Experiment) -> dict:
    """What the experiment page's Manipulations panel shows."""
    groups = sorted({(em.treatment_group or "").strip() for em in exp.memberships if (em.treatment_group or "").strip()})
    return {"steps": [step_dict(s) for s in exp.steps], "schedule": schedule(exp), "groups": groups,
            "kinds": [{"key": k, "label": v[0]} for k, v in KINDS.items()],
            "notebook_on": lab.feature_on(session, "notebook"),
            "notebook_page": _my_notebook_page(session, exp.id)}


def weight_table(session, exp: Experiment) -> dict:
    """Body weights by mouse and date, with each date's day number and each
    weight as a percentage of the mouse's first."""
    members = _members(exp)
    series = weights_by_mouse(session, [em.mouse.id for em in members])
    dates = sorted({w.weigh_date for ws in series.values() for w in ws})
    rows = []
    for em in members:
        by_date = {w.weigh_date: w.grams for w in series[em.mouse.id]}
        first = next((by_date[d] for d in dates if d in by_date), None)
        values = [by_date.get(d) for d in dates]
        rows.append({"mouse": em.mouse.id, "mouse_id": em.mouse.mouse_id, "group": em.treatment_group or "",
                     "sex": em.mouse.gender or "", "values": values,
                     "pct": [round(v / first * 100, 1) if (v is not None and first) else None for v in values]})
    start = exp.start_date
    return {"dates": [d.isoformat() for d in dates],
            "days": [((d - start).days + 1) if start else None for d in dates], "rows": rows}


def notebook_payload(session, exp: Experiment) -> dict:
    return {
        "id": exp.id, "name": exp.name, "status": exp.status, "owner": exp.owner_username,
        "description": exp.description, "treatment_plan": exp.treatment_plan,
        "start_date": exp.start_date.isoformat() if exp.start_date else "",
        "end_date": exp.end_date.isoformat() if exp.end_date else "",
        "url": url_for("experiment_detail", experiment_id=exp.id),
        "members": [{"mouse": em.mouse.id, "mouse_id": em.mouse.mouse_id, "group": em.treatment_group or "",
                     "sex": em.mouse.gender or "", "genotype": em.mouse.genotype or ""} for em in _members(exp)],
        "steps": [step_dict(s) for s in exp.steps],
        "schedule": schedule(exp),
        "weights": weight_table(session, exp),
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ---------------------------------------------------------------- calendar

def calendar_items(session, start: date, end: date, owner: str | None = None) -> list[dict]:
    """Days of manipulations not yet done, on the colony's calendar layer
    (done ones stay on the experiment). A personal feed gets its owner's."""
    query = select(Experiment).where(Experiment.status == "active", Experiment.start_date.is_not(None))
    if owner is not None:
        query = query.where(Experiment.owner_username == owner)
    out = []
    for exp in session.scalars(query):
        for row in schedule(exp):
            if row["state"] == "done" or not row["date"]:
                continue
            when = date.fromisoformat(row["date"])
            if not (start <= when <= end):
                continue
            who = f" · {row['group']}" if row["group"] else ""
            color = "#ff9f0a" if row["state"] == "overdue" else "#34c759"
            out.append({
                "id": f"auto-expstep-{row['step_id']}-{row['day']}", "kind": "auto", "calendarId": "auto",
                "title": f"{row['title']} · {exp.name}{who}", "category": "allday", "isAllday": True,
                "start": datetime.combine(when, datetime.min.time()).isoformat(),
                "end": datetime.combine(when, datetime.max.time()).isoformat(),
                "backgroundColor": color, "borderColor": color,
                "body": f"Day {row['day']} of {exp.name} ({row['group_size']} mice)",
                "isReadOnly": True,
                "raw": {"source": "experiment-step", "anchor_id": exp.id, "icon": row["icon"],
                        "href": url_for("experiment_detail", experiment_id=exp.id) + f"#day-{row['day']}"},
            })
    return out


# ---------------------------------------------------------------- saving

def _refuse(exp: Experiment):
    if access.can_edit_experiment(exp):
        return None
    return jsonify({"ok": False, "error": access.denied_message("experiment", exp.owner_username)}), 403


def _json():
    return request.get_json(silent=True) or request.form.to_dict()


@bp.post("/<int:experiment_id>/steps/save")
def save_step(experiment_id: int):
    data = _json()
    with SessionLocal() as s:
        exp = _load(s, experiment_id)
        refused = _refuse(exp)
        if refused:
            return refused
        try:
            days = parse_days(str(data.get("days", "")))
        except ValueError as error:
            return jsonify({"ok": False, "error": str(error)}), 400
        kind = str(data.get("kind") or "injection")
        if kind not in KINDS:
            return jsonify({"ok": False, "error": "Pick what kind of manipulation it is."}), 400
        agent = str(data.get("agent") or "").strip()[:200]
        if not agent and kind not in ("weigh", "behavior", "imaging", "surgery", "sample"):
            return jsonify({"ok": False, "error": "Say what is given, e.g. Tamoxifen or HDM."}), 400
        step_id = int(data.get("id") or 0)
        if step_id:
            step = s.get(ExperimentStep, step_id)
            if step is None or step.experiment_id_fk != exp.id:
                return jsonify({"ok": False, "error": "That manipulation is no longer there."}), 404
            gone = sorted(r.day for r in step.records if r.day not in days)
            if gone:
                return jsonify({"ok": False, "error": f"Day {days_label(gone)} is recorded as done: undo that "
                                                      "first to take the day out of the plan."}), 409
        else:
            step = ExperimentStep(experiment_id_fk=exp.id, created_by=g.user.username,
                                  position=len(exp.steps))
            s.add(step)
        step.days = days_label(days)
        step.kind = kind
        step.agent = agent
        step.dose = str(data.get("dose") or "").strip()[:80]
        step.route = str(data.get("route") or "").strip()[:60]
        step.concentration = str(data.get("concentration") or "").strip()[:60]
        step.treatment_group = str(data.get("group") or "").strip()[:80]
        step.notes = str(data.get("notes") or "").strip()
        exp.updated_at = datetime.utcnow()
        s.commit()
        s.refresh(exp)
        return jsonify({"ok": True, **page_data(s, exp)})


@bp.post("/<int:experiment_id>/steps/<int:step_id>/delete")
def delete_step(experiment_id: int, step_id: int):
    with SessionLocal() as s:
        exp = _load(s, experiment_id)
        refused = _refuse(exp)
        if refused:
            return refused
        step = s.get(ExperimentStep, step_id)
        if step is not None and step.experiment_id_fk == exp.id:
            if step.records and (_json().get("confirm") != "1"):
                return jsonify({"ok": False, "needs_confirm": True,
                                "error": f"{len(step.records)} day(s) of it are recorded as done."}), 409
            s.delete(step)
            s.commit()
            s.refresh(exp)
        return jsonify({"ok": True, **page_data(s, exp)})


@bp.get("/<int:experiment_id>/steps/<int:step_id>/day/<int(signed=True):day>")
def day_detail(experiment_id: int, step_id: int, day: int):
    """For the record dialog: the day's date, and each mouse it is for with
    its latest weight and the amount it gets."""
    from .app import can_edit_mouse
    with SessionLocal() as s:
        exp = _load(s, experiment_id)
        step = s.get(ExperimentStep, step_id)
        if step is None or step.experiment_id_fk != exp.id or day not in safe_days(step):
            abort(404)
        record = next((r for r in step.records if r.day == day), None)
        planned = day_date(exp.start_date, day)
        on = date.fromisoformat(request.args["on"]) if request.args.get("on") else (
            record.done_on if record else (planned if planned and planned <= date.today() else date.today()))
        members = _members(exp, step.treatment_group)
        series = weights_by_mouse(s, [em.mouse.id for em in members])
        given = {m.get("mouse") for m in (_record_dict(record)["mice"] if record else [])}
        mice = []
        for em in members:
            w = weight_on(series[em.mouse.id], on)
            today_weight = next((x.grams for x in series[em.mouse.id] if x.weigh_date == on), None)
            mice.append({
                "mouse": em.mouse.id, "mouse_id": em.mouse.mouse_id, "group": em.treatment_group or "",
                "sex": em.mouse.gender or "", "grams": w.grams if w else None,
                "weighed_on": w.weigh_date.isoformat() if w else "", "today_grams": today_weight,
                "can_weigh": can_edit_mouse(em.mouse),
                "given": (em.mouse.id in given) if record else True,
                **dose_for(step.dose, step.concentration, w.grams if w else None),
            })
        return jsonify({"ok": True, "step": step_dict(step), "day": day,
                        "planned": planned.isoformat() if planned else "", "on": on.isoformat(),
                        "record": _record_dict(record) if record else None, "mice": mice,
                        "editable": access.can_edit_experiment(exp)})


@bp.post("/<int:experiment_id>/steps/<int:step_id>/day/<int(signed=True):day>/record")
def record_day(experiment_id: int, step_id: int, day: int):
    """Record the day as done: the date, which mice (all of the group by
    default), and for a body-weight step, the weights."""
    from .app import can_edit_mouse
    data = request.get_json(silent=True) or {}
    with SessionLocal() as s:
        exp = _load(s, experiment_id)
        refused = _refuse(exp)
        if refused:
            return refused
        step = s.get(ExperimentStep, step_id)
        if step is None or step.experiment_id_fk != exp.id or day not in safe_days(step):
            abort(404)
        try:
            on = date.fromisoformat(str(data.get("done_on") or date.today().isoformat())[:10])
        except ValueError:
            return jsonify({"ok": False, "error": "That date isn't a date."}), 400
        if on > date.today():
            return jsonify({"ok": False, "error": "It can't be recorded as done on a day still to come."}), 400
        members = {em.mouse.id: em for em in _members(exp, step.treatment_group)}
        chosen = [int(m) for m in data.get("mice", list(members)) if int(m) in members]
        if not chosen:
            return jsonify({"ok": False, "error": "Tick the mice it was done to."}), 400
        problems = []
        if step.kind == "weigh":
            grams = data.get("grams") or {}
            for mouse_row in chosen:
                raw = str(grams.get(str(mouse_row), "")).strip().replace(",", ".")
                if not raw:
                    continue
                try:
                    value = float(raw)
                except ValueError:
                    return jsonify({"ok": False, "error": f"“{raw}” isn't a weight in grams."}), 400
                if not 0 < value < 200:
                    return jsonify({"ok": False, "error": f"{value} g isn't a mouse's weight."}), 400
                mouse = members[mouse_row].mouse
                if not can_edit_mouse(mouse):
                    problems.append(f"#{mouse.mouse_id}: {access.reason_denied(mouse)}")
                    continue
                existing = s.scalar(select(MouseWeight).where(MouseWeight.mouse_id_fk == mouse.id,
                                                              MouseWeight.weigh_date == on))
                if existing is None:
                    s.add(MouseWeight(mouse_id_fk=mouse.id, weigh_date=on, grams=value,
                                      notes=f"{exp.name}, day {day}"[:200], recorded_by=g.user.username))
                else:
                    existing.grams, existing.recorded_by = value, g.user.username
            s.flush()
        series = weights_by_mouse(s, chosen)
        mice = []
        for mouse_row in chosen:
            mouse = members[mouse_row].mouse
            w = weight_on(series[mouse_row], on)
            entry = {"mouse": mouse_row, "mouse_id": mouse.mouse_id, "grams": w.grams if w else None}
            if step.kind != "weigh":
                entry.update(dose_for(step.dose, step.concentration, w.grams if w else None))
            mice.append(entry)
        record = next((r for r in step.records if r.day == day), None)
        if record is None:
            record = ExperimentStepRecord(step_id_fk=step.id, day=day)
            s.add(record)
        record.done_on, record.done_by = on, g.user.username
        record.mice = json.dumps(mice)
        record.note = str(data.get("note") or "").strip()
        exp.updated_at = datetime.utcnow()
        s.commit()
        s.refresh(exp)
        return jsonify({"ok": True, "problems": problems, **page_data(s, exp)})


@bp.post("/<int:experiment_id>/steps/<int:step_id>/day/<int(signed=True):day>/undo")
def undo_day(experiment_id: int, step_id: int, day: int):
    """Back to not done. Weights recorded with it stay in the weight table."""
    with SessionLocal() as s:
        exp = _load(s, experiment_id)
        refused = _refuse(exp)
        if refused:
            return refused
        record = s.scalar(select(ExperimentStepRecord).join(ExperimentStep).where(
            ExperimentStep.experiment_id_fk == exp.id, ExperimentStepRecord.step_id_fk == step_id,
            ExperimentStepRecord.day == day))
        if record is not None:
            s.delete(record)
            s.commit()
            s.refresh(exp)
        return jsonify({"ok": True, **page_data(s, exp)})


# ---------------------------------------------------------------- the notebook

@bp.get("/<int:experiment_id>/notebook.json")
def notebook_json(experiment_id: int):
    with SessionLocal() as s:
        exp = _load(s, experiment_id)
        return jsonify({"ok": True, "experiment": notebook_payload(s, exp)})


@bp.get("/notebook-list.json")
def notebook_list():
    """Experiments to pick from in a notebook block: yours first."""
    me = g.user.username
    with SessionLocal() as s:
        rows = s.scalars(select(Experiment).order_by(Experiment.created_at.desc())).all()
        items = [{"id": e.id, "name": e.name, "status": e.status, "owner": e.owner_username,
                  "start_date": e.start_date.isoformat() if e.start_date else "",
                  "mice": len(e.memberships), "mine": e.owner_username == me} for e in rows]
    items.sort(key=lambda e: (not e["mine"], e["status"] != "active"))
    return jsonify({"ok": True, "experiments": items})


def _my_notebook_page(session, experiment_id: int) -> int | None:
    from .inventory_service import get_setting
    from .models import NotebookPage
    raw = get_setting(session, NOTEBOOK_PAGE_KEY.format(experiment=experiment_id, user=g.user.username), "")
    if not raw.isdigit():
        return None
    return int(raw) if session.get(NotebookPage, int(raw)) is not None else None


def block_markdown(experiment_id: int) -> str:
    return "```experiment\n" + json.dumps({"id": experiment_id, "show": ["plan", "weights"]}) + "\n```"


@bp.post("/<int:experiment_id>/notebook")
def add_to_notebook(experiment_id: int):
    """A notebook page for this experiment (yours), with its manipulations
    and body weights in it, live. The second time, that page again."""
    from . import lab_notebook as nb
    from .inventory_service import set_setting
    with SessionLocal() as s:
        exp = _load(s, experiment_id)
        if not lab.feature_on(s, "notebook"):
            flash("The notebook is switched off for this lab.", "error")
            return redirect(url_for("experiment_detail", experiment_id=exp.id))
        page_id = _my_notebook_page(s, exp.id)
        if page_id is None:
            tab = nb.tab_named(s, g.user.username, nb.EXPERIMENTS_TAB)
            lines = [f"Mouse experiment [{exp.name}]({url_for('experiment_detail', experiment_id=exp.id)})"
                     + (f", started {exp.start_date.isoformat()}" if exp.start_date else "") + ".", "",
                     block_markdown(exp.id), "", "## Notes", "", "## Deviations", ""]
            status = {"active": "running", "done": "done"}.get(exp.status, "planned")
            extra = {"status": status, **({"started_at": nb._now()} if status == "running" else {})}
            page = nb.new_page(s, tab, exp.name, "\n".join(lines), kind="experiment", **extra)
            nb.record_edit(s, page)
            set_setting(s, NOTEBOOK_PAGE_KEY.format(experiment=exp.id, user=g.user.username), str(page.id))
            s.commit()
            page_id = page.id
    return redirect(url_for("notebook", page=page_id))
