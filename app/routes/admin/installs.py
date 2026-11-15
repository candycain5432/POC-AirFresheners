"""Admin: log completed installs (cost, video, before/after photos) and edit them later."""
from flask import abort, flash, redirect, render_template, request, url_for

from ...extensions import db
from ...models import Install, InstallPhoto
from ...models.voting import TIER_LABELS, TIER_LEVELS
from ...services.clock import shop_today
from ...services.fund import active_goal, fund_summary
from ...services.installs import InstallError, delete_install_photo, log_install, update_install
from ...services.uploads import UploadError
from . import bp
from .forms import FormReader


@bp.route("/installs", methods=["GET", "POST"])
def installs():
    goal = active_goal()
    form = FormReader(request.form)
    if request.method == "GET":
        # Pre-fill from the part being funded: the usual case.
        form.values.update({
            "part_name": goal.part_name if goal else "", "tier": goal.tier if goal else "mid",
            "cost": f"{goal.goal_cents / 100:.2f}" if goal else "", "installed_on": shop_today().isoformat(),
            "completes_goal": "1" if goal else "",
        })
    else:
        part_name = form.text("part_name", "Part", max_len=120)
        tier = form.choice("tier", "Tier", TIER_LEVELS)
        cost = form.money("cost", "Cost")
        installed_on = form.date("installed_on", "Install date")
        notes = form.text("notes", "Notes", required=False, max_len=2000)
        video_url = form.text("video_url", "Video link", required=False, max_len=300)
        completes = form.checkbox("completes_goal")
        if not form.errors:
            try:
                install = log_install(
                    part_name, tier, cost, installed_on, video_url, notes,
                    before_files=request.files.getlist("before_photos"),
                    after_files=request.files.getlist("after_photos"),
                    completes_goal=goal if completes else None,
                )
            except (InstallError, UploadError) as error:
                form.errors["upload"] = str(error)
            else:
                flash(f"Install logged: {install.part_name}.", "success")
                return redirect(url_for("admin.installs"))
    return render_template(
        "admin/installs.html", form=form, goal=goal, fund=fund_summary(),
        installs=Install.query.order_by(Install.installed_on.desc()).all(),
        tier_levels=[(level, TIER_LABELS[level]) for level in TIER_LEVELS],
    ), (400 if form.errors else 200)


@bp.route("/installs/<int:install_id>", methods=["GET", "POST"])
def install_edit(install_id):
    install = db.session.get(Install, install_id)
    if install is None:
        abort(404)
    form = FormReader(request.form)
    if request.method == "GET":
        form.values.update({"video_url": install.video_url or "", "notes": install.notes or "",
                            "cost": f"{install.cost_cents / 100:.2f}"})
    else:
        video_url = form.text("video_url", "Video link", required=False, max_len=300)
        notes = form.text("notes", "Notes", required=False, max_len=2000)
        cost = form.money("cost", "Cost")
        if not form.errors:
            try:
                update_install(install, video_url, notes, cost,
                               before_files=request.files.getlist("before_photos"),
                               after_files=request.files.getlist("after_photos"))
            except (InstallError, UploadError) as error:
                form.errors["upload"] = str(error)
            else:
                flash("Install updated.", "success")
                return redirect(url_for("admin.install_edit", install_id=install.id))
    return render_template("admin/install_edit.html", install=install, form=form), (400 if form.errors else 200)


@bp.route("/install-photos/<int:photo_id>/delete", methods=["POST"])
def install_photo_delete(photo_id):
    photo = db.session.get(InstallPhoto, photo_id)
    if photo is None:
        abort(404)
    install_id = photo.install_id
    delete_install_photo(photo)
    flash("Photo removed.", "success")
    return redirect(url_for("admin.install_edit", install_id=install_id))
