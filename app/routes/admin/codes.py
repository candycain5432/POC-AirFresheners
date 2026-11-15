"""Admin: batches of freshener codes for fresheners sold in person (meet tables, shops)."""
import io
import zipfile

from flask import Response, abort, flash, redirect, render_template, request, url_for

from ...extensions import db
from ...models import CodeBatch
from ...services.codes import MAX_BATCH, batch_csv, create_batch, format_code
from ...services.qr import qr_data_uri, qr_png_bytes
from . import bp
from .forms import FormReader


def _batch_or_404(batch_id):
    batch = db.session.get(CodeBatch, batch_id)
    if batch is None:
        abort(404)
    return batch


def _vote_link(code):
    """What each QR code holds: the vote page with the code filled in."""
    return url_for("vote.index", code=code.code, _external=True)


@bp.route("/codes", methods=["GET", "POST"])
def codes():
    form = FormReader(request.form)
    if request.method == "POST":
        label = form.text("label", "Label", max_len=120)
        count = form.integer("count", "How many", 1, MAX_BATCH)
        if not form.errors:
            batch = create_batch(label, count)
            flash(f"Made {count} codes for “{label}”.", "success")
            return redirect(url_for("admin.code_batch", batch_id=batch.id))
    batches = CodeBatch.query.order_by(CodeBatch.created_at.desc()).all()
    return render_template("admin/codes.html", batches=batches, form=form, max_batch=MAX_BATCH), \
        (400 if form.errors else 200)


@bp.route("/codes/<int:batch_id>")
def code_batch(batch_id):
    batch = _batch_or_404(batch_id)
    return render_template("admin/code_batch.html", batch=batch, codes=sorted(batch.codes, key=lambda c: c.id))


@bp.route("/codes/<int:batch_id>/print")
def code_batch_print(batch_id):
    """A printable sheet of tags: QR code + code text. Use the browser's Print."""
    batch = _batch_or_404(batch_id)
    tags = [{"code": format_code(c.code), "qr": qr_data_uri(_vote_link(c), box_size=4)}
            for c in sorted(batch.codes, key=lambda c: c.id)]
    return render_template("admin/code_print.html", batch=batch, tags=tags,
                           vote_url=url_for("vote.index", _external=True))


@bp.route("/codes/<int:batch_id>.csv")
def code_batch_csv(batch_id):
    batch = _batch_or_404(batch_id)
    return Response(batch_csv(batch), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="codes-batch-{batch.id}.csv"'})


@bp.route("/codes/<int:batch_id>/qr.zip")
def code_batch_zip(batch_id):
    """One PNG per code (named after the code), for a print shop or label printer."""
    batch = _batch_or_404(batch_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for code in batch.codes:
            archive.writestr(f"{format_code(code.code)}.png", qr_png_bytes(_vote_link(code), box_size=10))
    return Response(buffer.getvalue(), mimetype="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="qr-codes-batch-{batch.id}.zip"'})
