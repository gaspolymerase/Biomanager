"""Pages for setting up the lab and for notifications.

  /setup            the first-run survey for the first admin, and afterwards
                    the admin's "Lab setup" page: databases, functions,
                    what members may do, who else is an admin
  /welcome          a short tour for anyone signing in for the first time
  /databases/<kind>/<key>/audience   share a personal database with the lab,
                    or make a lab database someone's own again
  /notifications    everything you were told, and the bell's data

See app/lab.py for the rules and app/notify.py for what sends notifications.
"""
from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import select

from . import lab, notify
from .db import SessionLocal
from .models import NotificationRecord, UserAccount

bp = Blueprint("lab", __name__)


@bp.app_template_filter("when")
def when(moment) -> str:
    """"just now", "5 min ago", "3 h ago", "yesterday", or the date.
    Times are stored in UTC."""
    if not moment:
        return ""
    seconds = (datetime.utcnow() - moment).total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    if seconds < 2 * 86400:
        return "yesterday"
    return moment.strftime("%d %b %Y") if seconds > 300 * 86400 else moment.strftime("%d %b")


@bp.app_context_processor
def _notification_labels():
    labels = {key: label for key, (label, _hint) in notify.CATEGORIES.items()}
    labels.update({"account": "Accounts", "general": "General"})
    return {"notification_labels": labels}


def _admin_or_redirect():
    if g.get("user") is None:
        return redirect(url_for("login", next=request.path))
    if g.user.role != "admin":
        flash("Only a lab admin can change the lab's setup.", "error")
        return redirect(url_for("home_dashboard"))
    return None


# ---------------------------------------------------------------- lab-wide checks on every request

@bp.before_app_request
def refuse_switched_off():
    """A function the lab switched off has no pages; its data is kept."""
    if g.get("user") is None:
        return None
    feature = lab.feature_for_path(request.path)
    if feature is None or lab.request_features().get(feature.key, True):
        return None
    message = f"{feature.label} is switched off for this lab."
    if g.user.role == "admin":
        message += " You can switch it on in Lab setup."
    if request.method != "GET" or request.headers.get("X-Autosave") == "1":
        return jsonify({"ok": False, "error": message}), 403
    flash(message, "error")
    return redirect(url_for("home_dashboard"))


@bp.before_app_request
def remind_once_a_day():
    """The daily "waiting for genotyping" note, made on someone's first
    page of the day (remembered in their session, so it costs one query)."""
    user = g.get("user")
    if user is None or request.method != "GET" or request.path.startswith(("/static", "/notifications/count")):
        return None
    today = date.today().isoformat()
    if session.get("reminded_on") == today:
        return None
    session["reminded_on"] = today
    with SessionLocal() as db_session:
        fresh = db_session.get(UserAccount, user.id)
        if fresh is not None and notify.daily_genotyping_reminder(db_session, fresh):
            db_session.commit()
    return None


# ---------------------------------------------------------------- setup survey / lab setup

@bp.route("/setup", methods=["GET", "POST"])
def setup():
    blocked = _admin_or_redirect()
    if blocked:
        return blocked
    with SessionLocal() as db_session:
        first_run = not lab.setup_done(db_session)
        if request.method == "POST":
            if request.form.get("action") == "module":
                module = lab.set_module_enabled(db_session, request.form.get("kind", ""), request.form.get("key", ""),
                                                request.form.get("enabled") == "1")
                if module is None:
                    abort(404)
                db_session.commit()
                flash(f"{module.label} {'switched on' if module.enabled else 'switched off'}.", "success")
                return redirect(url_for("lab.setup") + "#databases")
            switched_on = lab.apply_survey(db_session, request.form, g.user.username)
            if switched_on and not first_run:
                notify.tell_lab(db_session, g.user.username,
                                f"{g.user.display_name or g.user.username} added "
                                f"{', '.join(switched_on)} for the lab", link=url_for("home_dashboard"))
            user = db_session.get(UserAccount, g.user.id)
            if first_run and user.welcomed_at is None:
                user.welcomed_at = datetime.utcnow()
            db_session.commit()
            flash("The lab is set up. Change any of it here whenever you like." if first_run
                  else "Lab setup saved.", "success")
            return redirect(url_for("home_dashboard") if first_run else url_for("lab.setup"))
        state = lab.survey_state(db_session)
        custom = lab.custom_databases(db_session)
        admins = db_session.scalars(select(UserAccount).where(UserAccount.role == "admin",
                                                              UserAccount.disabled.is_(False))
                                    .order_by(UserAccount.username)).all()
        members = db_session.scalars(select(UserAccount).where(UserAccount.role == "member",
                                                               UserAccount.disabled.is_(False))
                                     .order_by(UserAccount.username)).all()
        return render_template(
            "lab/setup.html", first_run=first_run, state=state, custom=custom,
            features=lab.FEATURES, stock_choices=lab.STOCK_CHOICES, inventory_choices=lab.INVENTORY_CHOICES,
            permissions=lab.MEMBER_PERMISSIONS,
            admins=[{"id": a.id, "username": a.username, "name": a.display_name or a.username} for a in admins],
            members=[{"id": m.id, "username": m.username, "name": m.display_name or m.username} for m in members])


# ---------------------------------------------------------------- welcome tour

@bp.route("/welcome", methods=["GET", "POST"])
def welcome():
    if g.get("user") is None:
        return redirect(url_for("login", next=request.path))
    with SessionLocal() as db_session:
        if request.method == "POST":
            user = db_session.get(UserAccount, g.user.id)
            user.welcomed_at = datetime.utcnow()
            db_session.commit()
            from .app import landing_url
            return redirect(landing_url(user, after_welcome=True))
        name = lab.lab_name(db_session)
        may_create = lab.may_create_database(db_session)
        may_share = lab.may_create_lab_database(db_session)
    return render_template("lab/welcome.html", lab_name=name, may_create=may_create, may_share=may_share)


# ---------------------------------------------------------------- a database: mine or the lab's

@bp.route("/databases/<kind>/<key>/audience", methods=["POST"])
def audience(kind: str, key: str):
    if g.get("user") is None:
        return redirect(url_for("login"))
    with SessionLocal() as db_session:
        module = lab.module_for(db_session, kind, key)
        if module is None or not lab.can_see(module):
            abort(404)
        if not lab.can_change_audience(db_session, module):
            flash("Only a lab admin can change who sees this database.", "error")
            return redirect(url_for("organisms.index"))
        to = request.form.get("to")
        if to == "lab":
            module.private_to = ""
            notify.tell_lab(db_session, g.user.username,
                            f"{g.user.display_name or g.user.username} shared {module.label} with the lab")
            flash(f"{module.label} is now a lab database: everyone sees it.", "success")
        elif to == "me":
            owner = request.form.get("owner") or module.created_by or g.user.username
            if g.user.role != "admin":
                owner = g.user.username
            module.private_to = owner
            flash(f"{module.label} is now {'your' if owner == g.user.username else owner + chr(39) + 's'} "
                  "own database.", "success")
        db_session.commit()
    referrer = request.referrer or ""
    return redirect(referrer if referrer.startswith(request.host_url) else url_for("organisms.index"))


# ---------------------------------------------------------------- notifications

def _row(n: NotificationRecord) -> dict:
    return {"id": n.id, "title": n.title, "message": n.message, "category": n.category or "general",
            "link": n.link, "actor": n.actor, "is_read": n.is_read, "created_at": n.created_at}


@bp.route("/notifications")
def notifications():
    if g.get("user") is None:
        return redirect(url_for("login", next=request.path))
    show = request.args.get("show", "all")
    category = request.args.get("category", "")
    if category not in notify.CATEGORIES and category not in ("account", "general"):
        category = ""
    with SessionLocal() as db_session:
        rows = [_row(n) for n in notify.recent(db_session, g.user.username, limit=200,
                                               unread_only=(show == "unread"), category=category)]
        unread = notify.unread_count(db_session, g.user.username)
    return render_template("lab/notifications.html", rows=rows, show=show, category=category,
                           categories=notify.CATEGORIES, unread=unread)


@bp.route("/notifications/count")
def notification_count():
    if g.get("user") is None:
        return jsonify({"unread": 0}), 401
    with SessionLocal() as db_session:
        return jsonify({"unread": notify.unread_count(db_session, g.user.username)})


@bp.route("/notifications/panel")
def notification_panel():
    """The bell's dropdown, rendered on the server (fetched when opened)."""
    if g.get("user") is None:
        return "", 401
    with SessionLocal() as db_session:
        rows = [_row(n) for n in notify.recent(db_session, g.user.username, limit=8)]
        unread = notify.unread_count(db_session, g.user.username)
    return render_template("lab/_notification_panel.html", rows=rows, unread=unread)


@bp.route("/notifications/<int:note_id>/open")
def open_notification(note_id: int):
    """Mark it read and go where it points (only ever a page of this app)."""
    if g.get("user") is None:
        return redirect(url_for("login"))
    from .security import safe_next
    with SessionLocal() as db_session:
        note = db_session.get(NotificationRecord, note_id)
        if note is None or note.recipient_username != g.user.username:
            abort(404)
        note.is_read = True
        target = safe_next(note.link) or url_for("lab.notifications")
        db_session.commit()
    return redirect(target)
