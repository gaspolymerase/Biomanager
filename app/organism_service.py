"""Service layer for the configurable organism modules.

Everything a module does at runtime that is not a route: reading its JSON
configuration back into usable objects, seeding the built-in presets,
allocating record codes, turning schedule rules into an actual due list, and
counting a census.

The design rule here is that no function knows what species it is looking at.
Anything species-specific arrives as configuration on the module row.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select

from .models import (
    ModuleField,
    OrgCohort,
    OrgCross,
    OrgDue,
    OrgEvent,
    OrgHousing,
    OrgLine,
    OrgLocation,
    OrgMeasurement,
    OrgPreservationLot,
    Organism,
    OrganismModule,
)
from .organisms import (
    AUTO_SEED_PRESETS,
    CAPABILITY_BY_KEY,
    FIELD_TYPE_BY_KEY,
    PRESET_BY_KEY,
    PRESETS,
    normalize_capabilities,
)


# ---------------------------------------------------------------------------
# JSON helpers
#
# Config columns are Text so the schema is identical on SQLite and Postgres.
# These keep the "it might be malformed" handling in one place.
# ---------------------------------------------------------------------------


def load_list(raw: str | None) -> list:
    try:
        value = json.loads(raw or "[]")
        return value if isinstance(value, list) else []
    except (ValueError, TypeError):
        return []


def load_dict(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def dump(value) -> str:
    return json.dumps(value, separators=(",", ":"))


# ---------------------------------------------------------------------------
# The module view
#
# Templates should never call json.loads. `ModuleView` is the decoded, ready
# to render form of a module row, and it is what every route hands to Jinja.
# ---------------------------------------------------------------------------


@dataclass
class ModuleView:
    row: OrganismModule
    capabilities: set[str]
    schedule_rules: list[dict]
    housing_purposes: list[str]
    statuses: list[str]
    sexes: list[str]
    settings: dict

    # --- Passthroughs so templates can treat this as the module ----------
    @property
    def id(self) -> int: return self.row.id
    @property
    def key(self) -> str: return self.row.key
    @property
    def label(self) -> str: return self.row.label
    @property
    def label_plural(self) -> str: return self.row.label_plural or self.row.label
    @property
    def icon(self) -> str: return self.row.icon
    @property
    def blurb(self) -> str: return self.row.blurb
    @property
    def identity_mode(self) -> str: return self.row.identity_mode
    @property
    def age_unit(self) -> str: return self.row.age_unit
    @property
    def organism_noun(self) -> str: return self.row.organism_noun
    @property
    def organism_noun_plural(self) -> str: return self.row.organism_noun_plural
    @property
    def housing_noun(self) -> str: return self.row.housing_noun
    @property
    def housing_noun_plural(self) -> str: return self.row.housing_noun_plural
    @property
    def container_noun(self) -> str: return self.row.container_noun
    @property
    def line_noun(self) -> str: return self.row.line_noun
    @property
    def line_noun_plural(self) -> str: return self.row.line_noun_plural
    @property
    def cohort_noun(self) -> str: return self.row.cohort_noun
    @property
    def cohort_noun_plural(self) -> str: return self.row.cohort_noun_plural
    @property
    def cross_noun(self) -> str: return self.row.cross_noun

    def has(self, *keys: str) -> bool:
        """True when every named capability is enabled."""
        return all(k in self.capabilities for k in keys)

    def any_of(self, *keys: str) -> bool:
        return any(k in self.capabilities for k in keys)

    @property
    def tracks_individuals(self) -> bool:
        return self.identity_mode in ("individual", "hybrid")

    @property
    def tracks_groups(self) -> bool:
        return self.identity_mode in ("group", "hybrid")

    def rule(self, key: str) -> dict | None:
        return next((r for r in self.schedule_rules if r.get("key") == key), None)


def view(module: OrganismModule) -> ModuleView:
    return ModuleView(
        row=module,
        capabilities=set(load_list(module.capabilities)),
        schedule_rules=load_list(module.schedule_rules),
        housing_purposes=load_list(module.housing_purposes),
        statuses=load_list(module.statuses),
        sexes=load_list(module.sexes),
        settings=load_dict(module.settings),
    )


def list_modules(session, include_disabled: bool = False) -> list[OrganismModule]:
    stmt = select(OrganismModule).order_by(OrganismModule.position, OrganismModule.label)
    if not include_disabled:
        stmt = stmt.where(OrganismModule.enabled.is_(True))
    return list(session.scalars(stmt).all())


def get_module(session, key: str) -> OrganismModule | None:
    return session.scalar(select(OrganismModule).where(OrganismModule.key == key))


# ---------------------------------------------------------------------------
# Creating modules
# ---------------------------------------------------------------------------


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "").strip().lower()).strip("_")
    return slug or "organism"


def unique_key(session, base: str) -> str:
    key = slugify(base)
    if get_module(session, key) is None:
        return key
    for n in range(2, 60):
        candidate = f"{key}_{n}"
        if get_module(session, candidate) is None:
            return candidate
    return f"{key}_{int(datetime.utcnow().timestamp())}"


def create_module(session, spec: dict, created_by: str = "") -> OrganismModule:
    """Create a module from a plain dict.

    `spec` uses the same names as the preset dataclass, so the builder form
    and the presets go through one code path.
    """
    capabilities = normalize_capabilities(spec.get("capabilities") or [])
    identity = spec.get("identity_mode") or "hybrid"
    # Keep identity_mode and the capability flags consistent — they are two
    # views of the same decision and it is easy to set only one.
    if identity == "individual":
        capabilities = [c for c in capabilities if c != "group_counts"]
        if "individuals" not in capabilities:
            capabilities.append("individuals")
    elif identity == "group":
        capabilities = [c for c in capabilities if c != "individuals"]
        if "group_counts" not in capabilities:
            capabilities.append("group_counts")
    else:
        for needed in ("individuals", "group_counts"):
            if needed not in capabilities:
                capabilities.append(needed)
    capabilities = normalize_capabilities(capabilities)

    label = (spec.get("label") or "Organism").strip()
    module = OrganismModule(
        key=spec.get("key") or unique_key(session, label),
        label=label,
        label_plural=(spec.get("label_plural") or label).strip(),
        icon=spec.get("icon") or "circle-dashed",
        blurb=spec.get("blurb") or "",
        organism_noun=spec.get("organism_noun") or "animal",
        organism_noun_plural=spec.get("organism_noun_plural") or "animals",
        housing_noun=spec.get("housing_noun") or "enclosure",
        housing_noun_plural=spec.get("housing_noun_plural") or "enclosures",
        container_noun=spec.get("container_noun") or "rack",
        line_noun=spec.get("line_noun") or "line",
        line_noun_plural=spec.get("line_noun_plural") or "lines",
        cohort_noun=spec.get("cohort_noun") or "cohort",
        cohort_noun_plural=spec.get("cohort_noun_plural") or "cohorts",
        cross_noun=spec.get("cross_noun") or "cross",
        identity_mode=identity,
        age_unit=spec.get("age_unit") or "days",
        capabilities=dump(capabilities),
        schedule_rules=dump(spec.get("schedule_rules") or []),
        housing_purposes=dump(spec.get("housing_purposes") or []),
        statuses=dump(spec.get("statuses") or ["alive", "removed"]),
        sexes=dump(spec.get("sexes") or ["mixed", "female", "male", "unknown"]),
        settings=dump(spec.get("settings") or {}),
        preset_key=spec.get("preset_key") or "",
        position=int(spec.get("position") or 100),
        created_by=created_by,
    )
    session.add(module)
    session.flush()

    for position, field_spec in enumerate(spec.get("fields") or []):
        add_field(session, module, field_spec, position=position * 10)
    session.flush()
    return module


def add_field(session, module: OrganismModule, spec: dict, position: int | None = None) -> ModuleField | None:
    key = slugify(spec.get("key") or spec.get("label") or "")
    if not key or spec.get("field_type") not in FIELD_TYPE_BY_KEY:
        return None
    existing = session.scalar(
        select(ModuleField).where(
            ModuleField.module_id_fk == module.id,
            ModuleField.entity == (spec.get("entity") or "organism"),
            ModuleField.key == key,
        )
    )
    if existing is not None:
        return existing
    if position is None:
        highest = session.scalar(
            select(func.max(ModuleField.position)).where(ModuleField.module_id_fk == module.id)
        ) or 0
        position = highest + 10
    row = ModuleField(
        module_id_fk=module.id,
        entity=spec.get("entity") or "organism",
        key=key,
        label=(spec.get("label") or key).strip(),
        field_type=spec["field_type"],
        options=dump(spec.get("options") or []),
        default_value=spec.get("default_value") or "",
        help_text=spec.get("help_text") or "",
        required=bool(spec.get("required")),
        show_in_table=bool(spec.get("show_in_table")),
        position=position,
    )
    session.add(row)
    return row


def preset_spec(preset_key: str) -> dict:
    """A preset as the dict `create_module` expects."""
    preset = PRESET_BY_KEY.get(preset_key)
    if preset is None:
        return {}
    return {
        "key": preset.key,
        "preset_key": preset.key,
        "label": preset.label,
        "label_plural": preset.label_plural,
        "icon": preset.icon,
        "blurb": preset.blurb,
        "organism_noun": preset.organism_noun,
        "organism_noun_plural": preset.organism_noun_plural,
        "housing_noun": preset.housing_noun,
        "housing_noun_plural": preset.housing_noun_plural,
        "container_noun": preset.container_noun,
        "line_noun": preset.line_noun,
        "line_noun_plural": preset.line_noun_plural,
        "cohort_noun": preset.cohort_noun,
        "cohort_noun_plural": preset.cohort_noun_plural,
        "cross_noun": preset.cross_noun,
        "identity_mode": preset.identity_mode,
        "age_unit": preset.age_unit,
        "capabilities": list(preset.capabilities),
        "schedule_rules": [r.as_dict() for r in preset.schedule_rules],
        "housing_purposes": list(preset.housing_purposes),
        "statuses": list(preset.statuses),
        "sexes": list(preset.sexes),
        "fields": [dict(f) for f in preset.fields],
        "settings": dict(preset.settings),
    }


def seed_builtin_modules(session) -> list[str]:
    """Create the presets that have no hand-written module in this app.

    Mouse and zebrafish are deliberately excluded: they already ship as
    dedicated modules with live data, and seeding a second, empty copy would
    just be confusing. Both remain available in the builder.
    """
    created = []
    for position, preset_key in enumerate(AUTO_SEED_PRESETS):
        if get_module(session, preset_key) is not None:
            continue
        spec = preset_spec(preset_key)
        if not spec:
            continue
        spec["position"] = 200 + position
        create_module(session, spec, created_by="system")
        created.append(preset_key)
    return created


def repair_icon_names(session) -> int:
    """Rewrite icon names the sprite no longer has, in module rows and their
    schedule rules. Returns how many rows changed; idempotent."""
    from .icons import known, resolve

    names = known()
    if not names:
        return 0
    changed = 0
    for module in session.scalars(select(OrganismModule)):
        dirty = False
        if module.icon not in names:
            module.icon = resolve(module.icon)
            dirty = True
        rules = load_list(module.schedule_rules)
        for rule in rules:
            if rule.get("icon") and rule["icon"] not in names:
                rule["icon"] = resolve(rule["icon"])
                dirty = True
        if dirty:
            module.schedule_rules = dump(rules)
            changed += 1
    return changed


# ---------------------------------------------------------------------------
# Fields
# ---------------------------------------------------------------------------


def fields_for(session, module_id: int, entity: str) -> list[ModuleField]:
    return list(
        session.scalars(
            select(ModuleField)
            .where(ModuleField.module_id_fk == module_id, ModuleField.entity == entity)
            .order_by(ModuleField.position, ModuleField.id)
        ).all()
    )


def fields_by_entity(session, module_id: int) -> dict[str, list[ModuleField]]:
    rows = session.scalars(
        select(ModuleField)
        .where(ModuleField.module_id_fk == module_id)
        .order_by(ModuleField.position, ModuleField.id)
    ).all()
    grouped: dict[str, list[ModuleField]] = {}
    for row in rows:
        grouped.setdefault(row.entity, []).append(row)
    return grouped


def field_options(row: ModuleField) -> list[str]:
    return [str(v) for v in load_list(row.options)]


def read_attrs(form, field_rows: list[ModuleField], existing: dict | None = None) -> dict:
    """Pull this entity's custom field values out of a submitted form.

    Inputs are named `attr_<key>` so they cannot collide with the fixed
    columns. Only keys the module actually declares are accepted.
    """
    attrs = dict(existing or {})
    for row in field_rows:
        name = f"attr_{row.key}"
        if row.field_type == "checkbox":
            attrs[row.key] = bool(form.get(name))
            continue
        if name not in form:
            continue
        raw = (form.get(name) or "").strip()
        if row.field_type == "number":
            if raw == "":
                attrs[row.key] = None
            else:
                try:
                    attrs[row.key] = float(raw) if "." in raw else int(raw)
                except ValueError:
                    attrs[row.key] = raw
        else:
            attrs[row.key] = raw
    return attrs


def display_attr(row: ModuleField, attrs: dict):
    value = attrs.get(row.key)
    if row.field_type == "checkbox":
        return "Yes" if value else ""
    if value is None:
        return ""
    return value


# ---------------------------------------------------------------------------
# Codes
#
# Auto-allocated human-readable IDs, per module and per entity, e.g. the
# third vial in the Drosophila module becomes DROSOPHILA-V003. Labs that
# prefer their own scheme can always type over it.
# ---------------------------------------------------------------------------


ENTITY_MODELS = {
    "organism": Organism,
    "housing": OrgHousing,
    "line": OrgLine,
    "cohort": OrgCohort,
    "cross": OrgCross,
}
ENTITY_LETTER = {"organism": "A", "housing": "H", "line": "L", "cohort": "C", "cross": "X"}


def code_prefix(module: OrganismModule, entity: str) -> str:
    stem = re.sub(r"[^A-Z0-9]", "", module.key.upper())[:4] or "ORG"
    return f"{stem}-{ENTITY_LETTER.get(entity, 'A')}"


def next_code(session, module: OrganismModule, entity: str) -> str:
    model = ENTITY_MODELS.get(entity)
    if model is None:
        return ""
    prefix = code_prefix(module, entity)
    rows = session.scalars(
        select(model.code).where(
            model.module_id_fk == module.id, model.code.like(f"{prefix}%")
        )
    ).all()
    highest = 0
    for code in rows:
        match = re.search(r"(\d+)$", code or "")
        if match:
            highest = max(highest, int(match.group(1)))
    return f"{prefix}{highest + 1:03d}"


# ---------------------------------------------------------------------------
# Derived schedule
#
# A rule is (anchor date on a subject) + (offset in days). The offset can
# depend on the subject's rearing temperature, which is how one rule covers
# "flip flies every 14 days at 25 °C but every 28 at 18 °C".
# ---------------------------------------------------------------------------


RULE_SUBJECTS = {
    "cohort": OrgCohort,
    "housing": OrgHousing,
    "line": OrgLine,
    "organism": Organism,
}


def rule_offset(rule: dict, attrs: dict) -> int:
    offsets = rule.get("temp_offsets") or {}
    if offsets:
        temp = attrs.get("temperature_c")
        if temp not in (None, ""):
            key = str(temp).strip()
            if key in offsets:
                return int(offsets[key])
            # Nearest configured temperature, so an odd value still resolves.
            try:
                target = float(key)
                nearest = min(offsets, key=lambda k: abs(float(k) - target))
                return int(offsets[nearest])
            except (TypeError, ValueError):
                pass
    return int(rule.get("offset_days") or 0)


def recompute_due(session, module: OrganismModule) -> int:
    """Materialise outstanding schedule items for one module.

    Open (not-yet-done) rows are rebuilt from the current anchors so that
    editing a birth date moves the due date with it. Completed rows are left
    alone — they are the history of what was actually done.
    """
    mv = view(module)
    if not mv.has("schedule") or not mv.schedule_rules:
        return 0

    session.query(OrgDue).filter(
        OrgDue.module_id_fk == module.id, OrgDue.done_on.is_(None)
    ).delete(synchronize_session=False)

    created = 0
    for rule in mv.schedule_rules:
        model = RULE_SUBJECTS.get(rule.get("applies_to"))
        anchor = rule.get("anchor")
        if model is None or not anchor or not hasattr(model, anchor):
            continue

        stmt = select(model).where(model.module_id_fk == module.id)
        # Don't schedule work for things that are gone.
        if hasattr(model, "active"):
            stmt = stmt.where(model.active.is_(True))
        if hasattr(model, "retired"):
            stmt = stmt.where(model.retired.is_(False))
        if hasattr(model, "death_on"):
            stmt = stmt.where(model.death_on.is_(None))

        for subject in session.scalars(stmt).all():
            start = getattr(subject, anchor, None)
            if start is None:
                continue
            attrs = load_dict(getattr(subject, "attrs", "{}"))
            due_on = start + timedelta(days=rule_offset(rule, attrs))

            # A recurring rule that has been done before starts counting from
            # the last completion rather than the original anchor.
            last_done = session.scalar(
                select(func.max(OrgDue.done_on)).where(
                    OrgDue.module_id_fk == module.id,
                    OrgDue.rule_key == rule["key"],
                    OrgDue.subject_kind == rule["applies_to"],
                    OrgDue.subject_id == subject.id,
                )
            )
            if last_done is not None:
                if not rule.get("recurring"):
                    continue
                due_on = last_done + timedelta(days=rule_offset(rule, attrs))

            session.add(OrgDue(
                module_id_fk=module.id,
                subject_kind=rule["applies_to"],
                subject_id=subject.id,
                rule_key=rule["key"],
                due_on=due_on,
                assigned_to=getattr(subject, "owner", "") or "",
            ))
            created += 1
    return created


def due_items(session, module: OrganismModule, horizon_days: int = 14, include_done: bool = False):
    """Open schedule items due within the horizon, plus anything overdue."""
    mv = view(module)
    rules = {r["key"]: r for r in mv.schedule_rules}
    cutoff = date.today() + timedelta(days=horizon_days)

    stmt = select(OrgDue).where(OrgDue.module_id_fk == module.id)
    if not include_done:
        stmt = stmt.where(OrgDue.done_on.is_(None), OrgDue.due_on <= cutoff)
    rows = session.scalars(stmt.order_by(OrgDue.due_on)).all()

    # Resolve each subject's label in one pass per kind.
    wanted: dict[str, set[int]] = {}
    for row in rows:
        wanted.setdefault(row.subject_kind, set()).add(row.subject_id)
    labels: dict[tuple[str, int], str] = {}
    for kind, ids in wanted.items():
        model = RULE_SUBJECTS.get(kind)
        if model is None or not ids:
            continue
        for subject in session.scalars(select(model).where(model.id.in_(ids))).all():
            labels[(kind, subject.id)] = getattr(subject, "code", None) or f"#{subject.id}"

    today = date.today()
    out = []
    for row in rows:
        rule = rules.get(row.rule_key, {})
        out.append({
            "id": row.id,
            "rule_key": row.rule_key,
            "label": rule.get("label", row.rule_key.replace("_", " ").title()),
            "icon": rule.get("icon", "calendar-clock"),
            "subject_kind": row.subject_kind,
            "subject_id": row.subject_id,
            "subject_label": labels.get((row.subject_kind, row.subject_id), f"#{row.subject_id}"),
            "due_on": row.due_on,
            "days": (row.due_on - today).days,
            "overdue": row.due_on < today,
            "assigned_to": row.assigned_to,
            "done_on": row.done_on,
        })
    return out


def complete_due(session, module: OrganismModule, due_id: int, user: str) -> OrgDue | None:
    row = session.scalar(
        select(OrgDue).where(OrgDue.id == due_id, OrgDue.module_id_fk == module.id)
    )
    if row is None or row.done_on is not None:
        return None
    row.done_on = date.today()
    row.done_by = user

    # Roll the anchor forward so recurring maintenance restarts its clock.
    rule = view(module).rule(row.rule_key) or {}
    model = RULE_SUBJECTS.get(row.subject_kind)
    if rule.get("recurring") and model is not None:
        subject = session.get(model, row.subject_id)
        anchor = rule.get("anchor")
        if subject is not None and anchor and hasattr(subject, anchor):
            setattr(subject, anchor, date.today())

    log_event(session, module, row.subject_kind, row.subject_id, row.rule_key,
              recorded_by=user, notes=f"{rule.get('label', row.rule_key)} completed")
    return row


# ---------------------------------------------------------------------------
# Events and census
# ---------------------------------------------------------------------------


def log_event(session, module: OrganismModule, subject_kind: str, subject_id: int,
              event_type: str, occurred_on: date | None = None, count: int = 0,
              detail: dict | None = None, recorded_by: str = "", notes: str = "") -> OrgEvent:
    row = OrgEvent(
        module_id_fk=module.id,
        subject_kind=subject_kind,
        subject_id=subject_id,
        event_type=event_type,
        occurred_on=occurred_on or date.today(),
        count=count,
        detail=dump(detail or {}),
        recorded_by=recorded_by,
        notes=notes,
    )
    session.add(row)
    return row


def census(session, module: OrganismModule) -> dict:
    """Live counts for the module header.

    `animals` respects identity mode: summing `count` is correct for both an
    individually tracked animal (count=1) and a group of forty flies.
    """
    mid = module.id
    alive = select(func.coalesce(func.sum(Organism.count), 0)).where(
        Organism.module_id_fk == mid, Organism.death_on.is_(None)
    )
    return {
        "animals": session.scalar(alive) or 0,
        "records": session.scalar(
            select(func.count(Organism.id)).where(
                Organism.module_id_fk == mid, Organism.death_on.is_(None))
        ) or 0,
        "housing": session.scalar(
            select(func.count(OrgHousing.id)).where(
                OrgHousing.module_id_fk == mid, OrgHousing.active.is_(True))
        ) or 0,
        "lines": session.scalar(
            select(func.count(OrgLine.id)).where(
                OrgLine.module_id_fk == mid, OrgLine.retired.is_(False))
        ) or 0,
        "cohorts": session.scalar(
            select(func.count(OrgCohort.id)).where(OrgCohort.module_id_fk == mid)
        ) or 0,
        "crosses": session.scalar(
            select(func.count(OrgCross.id)).where(
                OrgCross.module_id_fk == mid, OrgCross.collected_on.is_(None))
        ) or 0,
        "overdue": session.scalar(
            select(func.count(OrgDue.id)).where(
                OrgDue.module_id_fk == mid, OrgDue.done_on.is_(None),
                OrgDue.due_on < date.today())
        ) or 0,
        "frozen_vials": session.scalar(
            select(func.coalesce(func.sum(OrgPreservationLot.vials_remaining), 0))
            .where(OrgPreservationLot.module_id_fk == mid)
        ) or 0,
    }


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------


def age_label(module: OrganismModule, start: date | None, end: date | None = None) -> str:
    """Age in the unit this organism's community actually uses."""
    if start is None:
        return ""
    days = ((end or date.today()) - start).days
    if days < 0:
        return ""
    unit = module.age_unit
    if unit == "weeks":
        return f"{days // 7}w"
    if unit == "dpf":
        return f"{days} dpf"
    if unit in ("generations", "passages"):
        return f"{days}d"
    return f"{days}d"


def capability_labels(module: OrganismModule) -> list[str]:
    return [
        CAPABILITY_BY_KEY[key].label
        for key in load_list(module.capabilities)
        if key in CAPABILITY_BY_KEY
    ]


def available_presets() -> list:
    """Presets for the builder, blank one last."""
    return sorted(PRESETS, key=lambda p: (p.key == "custom", p.label))


def location_tree(session, module_id: int) -> list[OrgLocation]:
    return list(
        session.scalars(
            select(OrgLocation)
            .where(OrgLocation.module_id_fk == module_id)
            .order_by(OrgLocation.kind, OrgLocation.name)
        ).all()
    )


# What to offer a module that turned on environment logging without saying
# which metrics it cares about. Covers the aquatic and incubator cases.
DEFAULT_ENVIRONMENT_METRICS = [
    {"key": "temperature_c", "label": "Temperature", "unit": "\u00b0C"},
    {"key": "ph", "label": "pH", "unit": ""},
    {"key": "conductivity", "label": "Conductivity", "unit": "\u00b5S"},
    {"key": "ammonia", "label": "Ammonia", "unit": "ppm"},
    {"key": "nitrite", "label": "Nitrite", "unit": "ppm"},
    {"key": "nitrate", "label": "Nitrate", "unit": "ppm"},
]


def measurement_metrics(module_view: ModuleView) -> list[dict]:
    """Environment metrics this module logs, from its settings."""
    metrics = module_view.settings.get("environment_metrics") or []
    clean = [m for m in metrics if isinstance(m, dict) and m.get("key")]
    return clean or list(DEFAULT_ENVIRONMENT_METRICS)


def metrics_to_text(metrics: list[dict]) -> str:
    """Render metrics for the Configure textarea: one `key:label:unit` per line."""
    return "\n".join(
        ":".join([m.get("key", ""), m.get("label", ""), m.get("unit", "")]).rstrip(":")
        for m in metrics
    )


def metrics_from_text(raw: str) -> list[dict]:
    """Parse `key:label:unit` lines back into metric dicts."""
    metrics = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(":")]
        key = slugify(parts[0])
        if not key:
            continue
        metrics.append({
            "key": key,
            "label": parts[1] if len(parts) > 1 and parts[1] else parts[0],
            "unit": parts[2] if len(parts) > 2 else "",
        })
    return metrics
