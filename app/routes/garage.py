"""
The Garage: a public grid of members' cars.

    GET       /garage/                 Car of the Month + the grid (?page=2 ...)
    GET       /garage/cars/<id>        one member's car
    GET/POST  /garage/join             enter a freshener code (rate limited)
    GET/POST  /garage/edit             create or edit the profile for that code
    POST      /garage/delete           delete that profile
    POST      /garage/leave            forget the code in this browser

The rules live in services/garage.py; photo safety in services/uploads.py.
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import GarageMember
from ..services import garage as garage_service
from ..services.codes import find_code
from ..services.rate_limit import client_ip, minutes_locked, record_failure
from ..services.uploads import UploadError

bp = Blueprint("garage", __name__, url_prefix="/garage")


@bp.route("/")
def index():
    page = request.args.get("page", 1, type=int)
    code = garage_service.code_in_session()
    return render_template(
        "garage/index.html",
        members=garage_service.visible_members(max(page, 1)),
        car_of_month=garage_service.current_car_of_month(),
        my_member=garage_service.member_for_code(code),
    )


@bp.route("/cars/<int:member_id>")
def car(member_id):
    member = db.session.get(GarageMember, member_id)
    if member is None or member.is_hidden:
        abort(404)
    cotm = garage_service.current_car_of_month()
    code = garage_service.code_in_session()
    return render_template(
        "garage/car.html",
        member=member,
        is_car_of_month=bool(cotm and cotm.member_id == member.id),
        is_mine=bool(code and member.code_id == code.id),
    )


@bp.route("/join", methods=["GET", "POST"])
def join():
    error = None
    status = 200
    if request.method == "POST":
        ip = client_ip()
        wait = minutes_locked(ip)
        if wait:
            error = (f"Too many wrong codes from this connection. "
                     f"Please wait about {wait} minute{'s' if wait != 1 else ''} and try again.")
            status = 429
        else:
            code = find_code(request.form.get("code", ""))
            if code is None:
                record_failure(ip)
                error = "We couldn't find that code. Check the tag on your freshener and try again."
                status = 400
            else:
                garage_service.remember_code(code)
                return redirect(url_for("garage.edit"))
    return render_template("garage/join.html", error=error), status


@bp.route("/edit", methods=["GET", "POST"])
def edit():
    code = garage_service.code_in_session()
    if code is None:
        return redirect(url_for("garage.join"))
    member = garage_service.member_for_code(code)

    values = {
        "owner_name": member.owner_name if member else "",
        "car_name": member.car_name if member else "",
        "description": member.description if member else "",
    }
    errors = {}
    if request.method == "POST":
        values, errors = garage_service.clean_form(request.form)
        if not errors:
            try:
                member = garage_service.save_profile(
                    code, values,
                    photo=request.files.get("photo"),
                    remove_photo=request.form.get("remove_photo") == "1",
                )
            except UploadError as problem:
                errors["photo"] = str(problem)
            else:
                flash("Your car is in the Garage!" if request.form.get("is_new") else "Saved.", "success")
                return redirect(url_for("garage.car", member_id=member.id))

    return render_template("garage/edit.html", member=member, values=values, errors=errors,
                           limits=garage_service.LIMITS), (400 if errors else 200)


@bp.route("/delete", methods=["POST"])
def delete():
    member = garage_service.member_for_code(garage_service.code_in_session())
    if member is None:
        return redirect(url_for("garage.join"))
    garage_service.delete_profile(member)
    garage_service.forget_code()
    flash("Your car has been removed from the Garage.", "success")
    return redirect(url_for("garage.index"))


@bp.route("/leave", methods=["POST"])
def leave():
    garage_service.forget_code()
    flash("Done. This browser no longer has your code.", "success")
    return redirect(url_for("garage.index"))
