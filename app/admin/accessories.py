from typing import Any, Optional

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.admin import admin_bp
from app.admin.boats import _save_photo_file
from app.factory import db
from app.models import Accessory, AccessoryCategory


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None or value.strip() == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _payload(form) -> dict[str, Any]:
    category_raw = form.get("category")
    try:
        category = AccessoryCategory(category_raw) if category_raw else None
    except ValueError:
        category = None
    return {
        "slug": (form.get("slug") or "").strip(),
        "title": (form.get("title") or "").strip(),
        "description": form.get("description") or "",
        "category": category,
        "price_usd": _parse_int(form.get("price_usd")) or 0,
        "previous_price_usd": _parse_int(form.get("previous_price_usd")),
        "stock": _parse_int(form.get("stock")) or 0,
        "active": form.get("active") == "on",
    }


@admin_bp.route("/accessories")
@login_required
def accessories_list() -> str:
    items = db.session.query(Accessory).order_by(Accessory.created_at.desc()).all()
    return render_template("admin/accessories_list.html", accessories=items)


@admin_bp.route("/accessories/new", methods=["GET", "POST"])
@login_required
def accessories_new() -> Any:
    if request.method == "POST":
        data = _payload(request.form)
        if not data["slug"] or not data["title"] or data["category"] is None:
            flash("Slug, título y categoría son obligatorios.", "error")
            return render_template(
                "admin/accessories_form.html",
                accessory=None,
                form=request.form,
                categories=list(AccessoryCategory),
            ), 400
        if db.session.query(Accessory).filter_by(slug=data["slug"]).first():
            flash("Ya existe un accesorio con ese slug.", "error")
            return render_template(
                "admin/accessories_form.html",
                accessory=None,
                form=request.form,
                categories=list(AccessoryCategory),
            ), 400
        accessory = Accessory(**data)
        photo_url = _save_photo_file(request.files.get("photo"))
        if photo_url:
            accessory.photo_url = photo_url
        db.session.add(accessory)
        db.session.commit()
        flash("Accesorio creado.", "success")
        return redirect(url_for("admin.accessories_edit", accessory_id=accessory.id))
    return render_template(
        "admin/accessories_form.html",
        accessory=None,
        form={},
        categories=list(AccessoryCategory),
    )


@admin_bp.route("/accessories/<int:accessory_id>/edit", methods=["GET", "POST"])
@login_required
def accessories_edit(accessory_id: int) -> Any:
    accessory = db.session.get(Accessory, accessory_id)
    if accessory is None:
        flash("Accesorio no encontrado.", "error")
        return redirect(url_for("admin.accessories_list"))
    if request.method == "POST":
        data = _payload(request.form)
        if not data["slug"] or not data["title"] or data["category"] is None:
            flash("Slug, título y categoría son obligatorios.", "error")
            return render_template(
                "admin/accessories_form.html",
                accessory=accessory,
                form=request.form,
                categories=list(AccessoryCategory),
            ), 400
        dup = (
            db.session.query(Accessory)
            .filter(Accessory.slug == data["slug"], Accessory.id != accessory.id)
            .first()
        )
        if dup:
            flash("Ya existe otro accesorio con ese slug.", "error")
            return render_template(
                "admin/accessories_form.html",
                accessory=accessory,
                form=request.form,
                categories=list(AccessoryCategory),
            ), 400
        for k, v in data.items():
            setattr(accessory, k, v)
        photo_url = _save_photo_file(request.files.get("photo"))
        if photo_url:
            accessory.photo_url = photo_url
        db.session.commit()
        flash("Accesorio actualizado.", "success")
        return redirect(url_for("admin.accessories_edit", accessory_id=accessory.id))
    return render_template(
        "admin/accessories_form.html",
        accessory=accessory,
        form={},
        categories=list(AccessoryCategory),
    )


@admin_bp.route("/accessories/<int:accessory_id>/delete", methods=["POST"])
@login_required
def accessories_delete(accessory_id: int) -> Any:
    accessory = db.session.get(Accessory, accessory_id)
    if accessory is None:
        flash("Accesorio no encontrado.", "error")
        return redirect(url_for("admin.accessories_list"))
    db.session.delete(accessory)
    db.session.commit()
    flash("Accesorio eliminado.", "success")
    return redirect(url_for("admin.accessories_list"))
