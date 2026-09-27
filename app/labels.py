"""QR codes and printable cage / tank / vial cards.

The gap this closes: the label on the physical cage and the record in the
database were separate things, so anyone at the rack had to walk back and
type an ID. Every comparable tool solves this the same way — put a scannable
code on the card that opens the record.

Two pieces:

  * `/labels/qr.svg?d=…` renders a QR as inline SVG. Pure Python via segno,
    no image libraries, no network, so it works in the packaged desktop app.
  * `/labels/cards/<kind>` lays those out on a printable sheet, sized for
    standard cage-card stock.

QR payloads are always absolute URLs built from the incoming request, so a
card printed from the lab server scans to the lab server rather than to
localhost.
"""
from __future__ import annotations

from datetime import date

from flask import Blueprint, Response, abort, g, redirect, request, url_for
from flask import render_template
from sqlalchemy import select

from .db import SessionLocal
from .models import CageRecord, OrgHousing, OrganismModule
from . import access
from . import organism_service as svc

bp = Blueprint("labels", __name__, url_prefix="/labels")

# Card sizes in millimetres, matched to common cage-card stock.
CARD_SIZES = {
    "cage": (100, 60),      # a typical mouse cage card
    "tank": (75, 45),       # aquatic tank label
    "vial": (50, 25),       # fly vial / plate label
}


@bp.before_request
def require_login():
    if g.get("user") is None:
        return redirect(url_for("login"))
    return None


def _qr_svg(payload: str, scale: int = 4) -> str:
    """Inline SVG for a QR code, or an empty string if segno is missing.

    segno is an optional dependency: without it the cards still print, just
    without the scannable part, which is better than a 500 at the printer.
    """
    try:
        import segno
    except ImportError:
        return ""
    # Error level M survives a smudged or partly peeled label.
    qr = segno.make(payload, error="m")
    return qr.svg_inline(scale=scale, border=0, dark="#15191d")


@bp.route("/qr.svg")
def qr_svg():
    """A single QR as a standalone SVG, for embedding anywhere."""
    payload = (request.args.get("d") or "").strip()
    if not payload:
        abort(400)
    try:
        scale = max(1, min(12, int(request.args.get("scale", 4))))
    except ValueError:
        scale = 4
    svg = _qr_svg(payload, scale)
    if not svg:
        abort(503)
    return Response(svg, mimetype="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"})


def _absolute(path: str) -> str:
    """Turn an app path into a URL that resolves from a phone on the LAN."""
    return request.url_root.rstrip("/") + path


@bp.route("/cards/cages")
def cage_cards():
    """Printable cards for mouse cages.

    `ids` selects specific cages; without it you get every cage in the
    current scope, which is the usual case after setting up a rack.
    """
    scope = access.resolve_scope(request.args.get("scope"))
    raw_ids = [i for i in (request.args.get("ids") or "").split(",") if i.strip().isdigit()]

    with SessionLocal() as session:
        stmt = select(CageRecord).order_by(CageRecord.cage_id)
        if raw_ids:
            stmt = stmt.where(CageRecord.id.in_([int(i) for i in raw_ids]))
        cages = [
            c for c in session.scalars(stmt).all()
            if raw_ids or access.in_scope(c, scope, shared=access.is_shared_cage(c))
        ]

        cards = []
        for cage in cages:
            living = [m for m in cage.mice if m.date_of_death is None]
            genotypes = sorted({(m.genotype or "").strip() for m in living if (m.genotype or "").strip()})
            # scope=all: a card is scanned by whoever is at the rack, and the
            # default "My colony" view would leave someone else's cage out.
            target = _absolute(url_for("colony", view="cages", scope="all", card=1) + f"#cage-{cage.id}")
            cards.append({
                "title": f"Cage {cage.cage_id}",
                "qr": _qr_svg(target, scale=3),
                "rows": [
                    ("Owner", cage.owner or "—"),
                    ("Purpose", cage.purpose or "—"),
                    ("Room", cage.room or cage.cage_location or "—"),
                    ("Animals", str(len(living))),
                    ("Genotype", "; ".join(genotypes)[:60] or "—"),
                    ("Card ID", cage.card_id or "—"),
                ],
                "shared": access.is_shared_cage(cage),
            })

    return render_template(
        "labels/cards.html",
        cards=cards,
        heading="Cage cards",
        size=CARD_SIZES["cage"],
        printed_on=date.today().isoformat(),
        back_url=url_for("colony", view="cages", scope=scope),
    )


@bp.route("/cards/<module_key>")
def module_cards(module_key: str):
    """Printable labels for a configurable organism module's housing units."""
    with SessionLocal() as session:
        module = svc.get_module(session, module_key)
        if module is None:
            abort(404)
        mv = svc.view(module)

        raw_ids = [i for i in (request.args.get("ids") or "").split(",") if i.strip().isdigit()]
        stmt = (select(OrgHousing)
                .where(OrgHousing.module_id_fk == module.id)
                .order_by(OrgHousing.code))
        if raw_ids:
            stmt = stmt.where(OrgHousing.id.in_([int(i) for i in raw_ids]))
        elif request.args.get("active", "1") == "1":
            stmt = stmt.where(OrgHousing.active.is_(True))
        units = session.scalars(stmt).all()

        fields = svc.fields_for(session, module.id, "housing")
        shown = [f for f in fields if f.show_in_table][:2]

        cards = []
        for unit in units:
            target = _absolute(
                url_for("organisms.module", key=module.key, view="housing") + f"#unit-{unit.id}")
            attrs = unit.attrs_dict
            rows = [
                (mv.line_noun.title(), unit.line.code if unit.line else "—"),
                ("Owner", unit.owner or "—"),
                ("Purpose", unit.purpose or "—"),
            ]
            rows += [(f.label, str(attrs.get(f.key, "") or "—")) for f in shown]
            if unit.last_serviced_on:
                rows.append(("Last serviced", unit.last_serviced_on.isoformat()))
            cards.append({
                "title": f"{mv.housing_noun.title()} {unit.code}",
                "qr": _qr_svg(target, scale=3),
                "rows": rows,
                "shared": False,
            })

    size = CARD_SIZES.get("vial" if mv.housing_noun in ("vial", "plate") else "tank")
    return render_template(
        "labels/cards.html",
        cards=cards,
        heading=f"{mv.label} · {mv.housing_noun} labels",
        size=size,
        printed_on=date.today().isoformat(),
        back_url=url_for("organisms.module", key=module.key, view="housing"),
    )
