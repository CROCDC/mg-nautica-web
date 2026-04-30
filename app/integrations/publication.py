"""Shared text builder for all social/marketplace publication platforms.

All platforms use the same title format and body structure.
Each platform's service calls build_caption() to get the full post text.
"""
from app.models.enums import BoatType, HullMaterial

_BOAT_TYPE_ES: dict[str, str] = {
    BoatType.SAILBOAT:  "Velero",
    BoatType.MOTORBOAT: "Lancha",
    BoatType.CRUISER:   "Crucero",
    BoatType.CATAMARAN: "Catamarán",
    BoatType.YACHT:     "Yate",
    BoatType.WHALER:    "Ballenera",
    BoatType.OTHER:     "Embarcación",
}

_HULL_MATERIAL_ES: dict[str, str] = {
    HullMaterial.FIBERGLASS:   "Fibra de vidrio",
    HullMaterial.WOOD:         "Madera",
    HullMaterial.FERROCEMENT:  "Ferrocemento",
    HullMaterial.ALUMINUM:     "Aluminio",
    HullMaterial.STEEL:        "Acero",
    HullMaterial.OTHER:        "Otro",
}

_SAIL_TYPES = {BoatType.SAILBOAT, BoatType.CATAMARAN}


def build_title(boat) -> str:
    """First line of the post: price | type EN VENTA – model."""
    if not boat.price_usd or boat.price_usd <= 0:
        raise ValueError(
            f"No se puede publicar '{boat.title}': el precio debe ser mayor a 0"
        )
    precio = f"{int(boat.price_usd):,}".replace(",", ".")
    tipo = _BOAT_TYPE_ES.get(boat.boat_type, "Embarcación").upper()
    modelo = (boat.model_name or boat.title or "").upper()
    return f"U$S {precio} | {tipo} EN VENTA – {modelo}"


def build_body(boat) -> str:
    """Structured body from intro paragraph through CONSULTAS section."""
    sections: list[str] = []

    if boat.description:
        intro = boat.description.strip()
        if intro:
            sections.append(intro)

    # DATOS GENERALES
    datos: list[str] = []
    if boat.shipyard:
        datos.append(f"Astillero: {boat.shipyard}")
    if boat.model_name:
        datos.append(f"Modelo: {boat.model_name}")
    if boat.year:
        datos.append(f"Año: {boat.year}")
    if boat.length_m is not None:
        datos.append(f"Eslora: {_fmt_m(boat.length_m)} mts")
    if boat.beam_m is not None:
        datos.append(f"Manga: {_fmt_m(boat.beam_m)} mts")
    if boat.draft_m is not None:
        datos.append(f"Calado: {_fmt_m(boat.draft_m)} mts")
    if boat.hull_material:
        material = _HULL_MATERIAL_ES.get(boat.hull_material) or boat.hull_material.value
        datos.append(f"Material: {material}")
    if datos:
        sections.append("DATOS GENERALES\n" + "\n".join(datos))

    specs = boat.specs

    # MOTOR Y CAPACIDADES
    motor: list[str] = []
    if specs:
        motor_parts: list[str] = []
        if specs.engine_brand:
            motor_parts.append(specs.engine_brand)
        if specs.engine_hp:
            motor_parts.append(f"{specs.engine_hp} HP")
        if motor_parts:
            motor.append(f"Motor: {' '.join(motor_parts)}")
        if specs.engine_hours:
            motor.append(f"Horas de motor: {specs.engine_hours} hs")
        if specs.propeller:
            motor.append(f"Hélice: {specs.propeller}")
        if specs.bow_thruster:
            motor.append("Bow thruster")
        if specs.fuel_liters:
            motor.append(f"Tanque de combustible: {specs.fuel_liters} L")
        if specs.fresh_water_liters:
            motor.append(f"Tanque de agua: {specs.fresh_water_liters} L")
    if motor:
        sections.append("MOTOR Y CAPACIDADES\n" + "\n".join(motor))

    # INTERIOR Y CONFORT
    interior: list[str] = []
    if specs:
        if specs.cabins_qty:
            interior.append(f"{specs.cabins_qty} camarote{'s' if specs.cabins_qty > 1 else ''}")
        if specs.bathrooms_qty:
            interior.append(f"{specs.bathrooms_qty} baño{'s' if specs.bathrooms_qty > 1 else ''}")
        if specs.saloon:
            interior.append(specs.saloon)
        if specs.galley:
            interior.append(specs.galley)
        if specs.fridge:
            interior.append(specs.fridge)
        if specs.air_conditioning:
            interior.append(specs.air_conditioning)
        if specs.water_heater:
            interior.append(specs.water_heater)
        if specs.tv:
            interior.append(specs.tv)
    if interior:
        sections.append("INTERIOR Y CONFORT\n" + "\n".join(interior))

    # NAVEGACIÓN Y VELAMEN (veleros y catamaranes únicamente)
    if boat.boat_type in _SAIL_TYPES and specs:
        vela: list[str] = []
        if specs.mast_rig:
            vela.append(f"Aparejo {specs.mast_rig}")
        if specs.sails:
            vela.append(specs.sails)
        if specs.furlers:
            vela.append(specs.furlers)
        if specs.poles:
            vela.append(specs.poles)
        if specs.bowsprit:
            vela.append(specs.bowsprit)
        if vela:
            sections.append("NAVEGACIÓN Y VELAMEN\n" + "\n".join(vela))

    # CONDICIONES
    if boat.commission_pct:
        pct = f"{float(boat.commission_pct):g}"
        sections.append(f"CONDICIONES\nComisión MG Náutica: {pct}% sobre el valor de venta")

    # CONSULTAS
    sections.append("CONSULTAS\nContactanos para más información, fotos y coordinar visita")

    return "\n\n".join(sections)


def build_caption(boat) -> str:
    """Full post text: title line + blank line + body."""
    return build_title(boat) + "\n\n" + build_body(boat)


def _fmt_m(val) -> str:
    """Format a measurement value with comma as decimal separator."""
    return f"{float(val):.2f}".replace(".", ",")
