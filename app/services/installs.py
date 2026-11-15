"""
Logging completed installs on the Revival Car (admin).

An install is money OUT of the fund (its cost) plus the story: video link,
notes and before/after photos. Logging the install of the part being funded
marks that goal "installed" and promotes the next queued goal (a vote
winner waiting its turn) to the progress bar.
"""
from ..extensions import db
from ..models import Install, InstallPhoto
from .embeds import embed_info
from .fund import activate_next_goal
from .uploads import UploadError, delete_upload, save_image


class InstallError(ValueError):
    pass


def check_video_url(url):
    """Empty is fine (video coming later); otherwise it must be a YouTube or TikTok link we can embed."""
    url = (url or "").strip()
    if url and embed_info(url) is None:
        raise InstallError("Video link must be a YouTube or TikTok video URL (or leave it empty for now).")
    return url


def _save_photos(files, kind, saved):
    photos = []
    for file in files:
        if file and file.filename:
            path = save_image(file, "installs")
            saved.append(path)
            photos.append(InstallPhoto(kind=kind, filename=path))
    return photos


def add_photos(install, before_files=(), after_files=()):
    """Validate and store photos; if any one is refused, none are kept."""
    saved = []
    try:
        photos = _save_photos(before_files, "before", saved) + _save_photos(after_files, "after", saved)
    except UploadError:
        for path in saved:
            delete_upload(path)
        raise
    install.photos.extend(photos)


def log_install(part_name, tier, cost_cents, installed_on, video_url="", notes="",
                before_files=(), after_files=(), completes_goal=None):
    install = Install(part_name=part_name, tier=tier, cost_cents=cost_cents, installed_on=installed_on,
                      video_url=check_video_url(video_url), notes=notes, goal=completes_goal)
    add_photos(install, before_files, after_files)
    db.session.add(install)
    if completes_goal is not None:
        completes_goal.status = "installed"
        db.session.flush()
        activate_next_goal()   # the queued vote winner (if any) is now being funded
    db.session.commit()
    return install


def update_install(install, video_url, notes, cost_cents, before_files=(), after_files=()):
    install.video_url = check_video_url(video_url)
    install.notes = notes
    install.cost_cents = cost_cents
    add_photos(install, before_files, after_files)
    db.session.commit()


def delete_install_photo(photo):
    delete_upload(photo.filename)
    db.session.delete(photo)
    db.session.commit()
