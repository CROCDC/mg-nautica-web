from decimal import Decimal
from typing import Any, Optional

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.admin import admin_bp
from app.factory import db
from app.models import (
    Boat,
    BoatPhoto,
    BoatSpecs,
    BoatStatus,
    BoatType,
    Flag,
    HullMaterial,
)


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None or value.strip() == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_decimal(value: Optional[str]) -> Optional[Decimal]:
    if value is None or value.strip() == "":
        return None
    try:
        return Decimal(value)
    except Exception:
        return None


def _parse_enum(enum_cls: type, value: Optional[str]):
    if not value:
        return None
    try:
        return enum_cls(value)
    except ValueError:
        return None


def _boat_payload(form) -> dict[str, Any]:
    return {
        "slug": (form.get("slug") or "").strip(),
        "title": (form.get("title") or "").strip(),
        "description": form.get("description") or "",
        "boat_type": _parse_enum(BoatType, form.get("boat_type")),
        "flag": _parse_enum(Flag, form.get("flag")),
        "country_location": form.get("country_location") or None,
        "city_location": form.get("city_location") or None,
        "zone": form.get("zone") or None,
        "year": _parse_int(form.get("year")),
        "shipyard": form.get("shipyard") or None,
        "model_name": form.get("model_name") or None,
        "hull_material": _parse_enum(HullMaterial, form.get("hull_material")),
        "length_m": _parse_decimal(form.get("length_m")),
        "beam_m": _parse_decimal(form.get("beam_m")),
        "draft_m": _parse_decimal(form.get("draft_m")),
        "displacement_t": _parse_decimal(form.get("displacement_t")),
        "price_usd": _parse_int(form.get("price_usd")) or 0,
        "previous_price_usd": _parse_int(form.get("previous_price_usd")),
        "on_sale": form.get("on_sale") == "on",
        "commission_pct": _parse_decimal(form.get("commission_pct")),
        "commission_flat_usd": _parse_int(form.get("commission_flat_usd")),
        "status": _parse_enum(BoatStatus, form.get("status")) or BoatStatus.AVAILABLE,
        "featured": form.get("featured") == "on",
        "last_refit": form.get("last_refit") or None,
        "last_careening": form.get("last_careening") or None,
    }


@admin_bp.route("/boats")
@login_required
def boats_list() -> str:
    q = (request.args.get("q") or "").strip()
    query = db.session.query(Boat)
    if q:
        term = f"%{q.lower()}%"
        query = query.filter(db.func.lower(Boat.title).like(term))
    boats = query.order_by(Boat.created_at.desc()).all()
    return render_template("admin/boats_list.html", boats=boats, q=q)


@admin_bp.route("/boats/new", methods=["GET", "POST"])
@login_required
def boats_new() -> Any:
    if request.method == "POST":
        data = _boat_payload(request.form)
        if not data["slug"] or not data["title"] or data["boat_type"] is None or data["flag"] is None:
            flash("Slug, título, tipo y bandera son obligatorios.", "error")
            return render_template(
                "admin/boats_form.html",
                boat=None,
                form=request.form,
                boat_types=list(BoatType),
                flags=list(Flag),
                hull_materials=list(HullMaterial),
                statuses=list(BoatStatus),
            ), 400
        if db.session.query(Boat).filter_by(slug=data["slug"]).first():
            flash(f"Ya existe una embarcación con el slug {data['slug']!r}.", "error")
            return render_template(
                "admin/boats_form.html",
                boat=None,
                form=request.form,
                boat_types=list(BoatType),
                flags=list(Flag),
                hull_materials=list(HullMaterial),
                statuses=list(BoatStatus),
            ), 400
        boat = Boat(**data)
        db.session.add(boat)
        db.session.flush()
        photo_url = (request.form.get("photo_url") or "").strip()
        if photo_url:
            db.session.add(BoatPhoto(boat_id=boat.id, url=photo_url, position=0, is_primary=True))
        db.session.commit()
        flash("Embarcación creada.", "success")
        return redirect(url_for("admin.boats_edit", boat_id=boat.id))
    return render_template(
        "admin/boats_form.html",
        boat=None,
        form={},
        boat_types=list(BoatType),
        flags=list(Flag),
        hull_materials=list(HullMaterial),
        statuses=list(BoatStatus),
    )


@admin_bp.route("/boats/<int:boat_id>/edit", methods=["GET", "POST"])
@login_required
def boats_edit(boat_id: int) -> Any:
    boat = db.session.get(Boat, boat_id)
    if boat is None:
        flash("Embarcación no encontrada.", "error")
        return redirect(url_for("admin.boats_list"))

    if request.method == "POST":
        data = _boat_payload(request.form)
        if not data["slug"] or not data["title"] or data["boat_type"] is None or data["flag"] is None:
            flash("Slug, título, tipo y bandera son obligatorios.", "error")
            return render_template(
                "admin/boats_form.html",
                boat=boat,
                form=request.form,
                boat_types=list(BoatType),
                flags=list(Flag),
                hull_materials=list(HullMaterial),
                statuses=list(BoatStatus),
            ), 400
        dup = (
            db.session.query(Boat)
            .filter(Boat.slug == data["slug"], Boat.id != boat.id)
            .first()
        )
        if dup:
            flash(f"Ya existe otra embarcación con el slug {data['slug']!r}.", "error")
            return render_template(
                "admin/boats_form.html",
                boat=boat,
                form=request.form,
                boat_types=list(BoatType),
                flags=list(Flag),
                hull_materials=list(HullMaterial),
                statuses=list(BoatStatus),
            ), 400
        for k, v in data.items():
            setattr(boat, k, v)
        db.session.commit()
        flash("Embarcación actualizada.", "success")
        return redirect(url_for("admin.boats_edit", boat_id=boat.id))

    return render_template(
        "admin/boats_form.html",
        boat=boat,
        form={},
        boat_types=list(BoatType),
        flags=list(Flag),
        hull_materials=list(HullMaterial),
        statuses=list(BoatStatus),
    )


@admin_bp.route("/boats/<int:boat_id>/delete", methods=["POST"])
@login_required
def boats_delete(boat_id: int) -> Any:
    boat = db.session.get(Boat, boat_id)
    if boat is None:
        flash("Embarcación no encontrada.", "error")
        return redirect(url_for("admin.boats_list"))
    db.session.delete(boat)
    db.session.commit()
    flash("Embarcación eliminada.", "success")
    return redirect(url_for("admin.boats_list"))


@admin_bp.route("/boats/<int:boat_id>/photos/add", methods=["POST"])
@login_required
def boats_photo_add(boat_id: int) -> Any:
    boat = db.session.get(Boat, boat_id)
    if boat is None:
        flash("Embarcación no encontrada.", "error")
        return redirect(url_for("admin.boats_list"))
    url = (request.form.get("url") or "").strip()
    if not url:
        flash("URL de foto vacía.", "error")
        return redirect(url_for("admin.boats_edit", boat_id=boat.id))
    max_pos = max((p.position for p in boat.photos), default=-1)
    db.session.add(
        BoatPhoto(
            boat_id=boat.id,
            url=url,
            alt=request.form.get("alt") or None,
            position=max_pos + 1,
            is_primary=not boat.photos,
        )
    )
    db.session.commit()
    flash("Foto agregada.", "success")
    return redirect(url_for("admin.boats_edit", boat_id=boat.id))


@admin_bp.route("/boats/<int:boat_id>/photos/<int:photo_id>/delete", methods=["POST"])
@login_required
def boats_photo_delete(boat_id: int, photo_id: int) -> Any:
    photo = db.session.get(BoatPhoto, photo_id)
    if photo is None or photo.boat_id != boat_id:
        flash("Foto no encontrada.", "error")
        return redirect(url_for("admin.boats_edit", boat_id=boat_id))
    db.session.delete(photo)
    db.session.commit()
    flash("Foto eliminada.", "success")
    return redirect(url_for("admin.boats_edit", boat_id=boat_id))


SPEC_STRING_FIELDS = [
    "engine_brand",
    "propeller",
    "sails",
    "furlers",
    "poles",
    "bowsprit",
    "mast_rig",
    "electronics_plotter",
    "electronics_ais",
    "electronics_radar",
    "electronics_wind",
    "electronics_autopilot",
    "electronics_charts",
    "electronics_vhf",
    "electronics_satellite",
    "batteries_config",
    "chargers",
    "generator",
    "saloon",
    "galley",
    "fridge",
    "tv",
    "air_conditioning",
    "water_heater",
    "ground_tackle",
    "extra_inventory",
]
SPEC_INT_FIELDS = [
    "engine_hp",
    "engine_hours",
    "fuel_liters",
    "fresh_water_liters",
    "solar_watts",
    "inverter_watts",
    "cabins_qty",
    "bathrooms_qty",
    "chain_meters",
    "chain_mm",
]
SPEC_BOOL_FIELDS = ["bow_thruster", "electronics_starlink"]


@admin_bp.route("/boats/<int:boat_id>/specs", methods=["POST"])
@login_required
def boats_specs_save(boat_id: int) -> Any:
    boat = db.session.get(Boat, boat_id)
    if boat is None:
        flash("Embarcación no encontrada.", "error")
        return redirect(url_for("admin.boats_list"))
    specs = boat.specs or BoatSpecs(boat_id=boat.id)
    for f in SPEC_STRING_FIELDS:
        val = request.form.get(f)
        setattr(specs, f, val if (val or "").strip() else None)
    for f in SPEC_INT_FIELDS:
        setattr(specs, f, _parse_int(request.form.get(f)))
    for f in SPEC_BOOL_FIELDS:
        setattr(specs, f, request.form.get(f) == "on")
    if boat.specs is None:
        db.session.add(specs)
    db.session.commit()
    flash("Ficha técnica guardada.", "success")
    return redirect(url_for("admin.boats_edit", boat_id=boat.id))
