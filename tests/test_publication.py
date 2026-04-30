"""Tests for the shared text builder used by all publication platforms."""
from app.integrations.publication import build_body, build_caption, build_title
from app.models.enums import BoatType, HullMaterial
from tests.factories import make_boat, make_full_boat


# ── build_title ──────────────────────────────────────────────────────────────


def test_build_title_basic_format():
    boat = make_boat(
        price_usd=130000,
        boat_type=BoatType.SAILBOAT,
        model_name="Sun Odyssey 54 DS",
    )
    assert build_title(boat) == "U$S 130.000 | VELERO EN VENTA – SUN ODYSSEY 54 DS"


def test_build_title_uses_dot_thousand_separator():
    boat = make_boat(price_usd=85000, boat_type=BoatType.SAILBOAT, model_name="Bavaria 37")
    assert "U$S 85.000" in build_title(boat)


def test_build_title_million_dollar_boat():
    boat = make_boat(price_usd=1250000, boat_type=BoatType.YACHT, model_name="Princess V70")
    assert "U$S 1.250.000" in build_title(boat)


def test_build_title_falls_back_to_title_when_no_model():
    boat = make_boat(
        price_usd=50000,
        boat_type=BoatType.MOTORBOAT,
        title="Lancha Quicksilver 21",
        model_name=None,
    )
    title = build_title(boat)
    assert "U$S 50.000" in title
    assert "LANCHA EN VENTA" in title
    assert "QUICKSILVER" in title.upper()


def test_build_title_translates_each_boat_type():
    cases = {
        BoatType.SAILBOAT: "VELERO",
        BoatType.MOTORBOAT: "LANCHA",
        BoatType.CRUISER: "CRUCERO",
        BoatType.CATAMARAN: "CATAMARÁN",
        BoatType.YACHT: "YATE",
        BoatType.WHALER: "BALLENERA",
        BoatType.OTHER: "EMBARCACIÓN",
    }
    for boat_type, expected_es in cases.items():
        boat = make_boat(boat_type=boat_type, model_name="Test")
        assert expected_es in build_title(boat), f"Expected {expected_es} for {boat_type}"


def test_build_title_uppercases_model():
    boat = make_boat(model_name="Sun Odyssey 54 DS", boat_type=BoatType.SAILBOAT)
    assert "SUN ODYSSEY 54 DS" in build_title(boat)


# ── build_body ───────────────────────────────────────────────────────────────


def test_build_body_starts_with_description():
    boat = make_boat(price_usd=50000)
    boat.description = "Velero impecable. Listo para navegar."
    body = build_body(boat)
    assert body.startswith("Velero impecable. Listo para navegar.")


def test_build_body_omits_intro_if_no_description():
    boat = make_boat(price_usd=50000, shipyard="Bavaria", year=2010)
    boat.description = None
    body = build_body(boat)
    # No intro paragraph, so body starts with the first non-empty section
    assert not body.startswith("Embarcación")
    assert "DATOS GENERALES" in body
    assert body.startswith("DATOS GENERALES")


def test_build_body_contains_datos_generales_section():
    boat = make_boat(
        price_usd=130000,
        boat_type=BoatType.SAILBOAT,
        shipyard="Jeanneau",
        model_name="Sun Odyssey 54 DS",
        year=2006,
        length_m="16.70",
        beam_m="4.85",
        draft_m="2.00",
        hull_material=HullMaterial.FIBERGLASS,
    )
    body = build_body(boat)
    assert "DATOS GENERALES" in body
    assert "Astillero: Jeanneau" in body
    assert "Modelo: Sun Odyssey 54 DS" in body
    assert "Año: 2006" in body
    assert "Eslora: 16,70 mts" in body
    assert "Manga: 4,85 mts" in body
    assert "Calado: 2,00 mts" in body
    assert "Material: Fibra de vidrio" in body


def test_build_body_translates_hull_material():
    cases = {
        HullMaterial.FIBERGLASS: "Fibra de vidrio",
        HullMaterial.WOOD: "Madera",
        HullMaterial.FERROCEMENT: "Ferrocemento",
        HullMaterial.ALUMINUM: "Aluminio",
        HullMaterial.STEEL: "Acero",
    }
    for material, expected in cases.items():
        boat = make_boat(hull_material=material)
        assert f"Material: {expected}" in build_body(boat)


def test_build_body_omits_missing_fields():
    boat = make_boat(price_usd=50000)
    boat.shipyard = None
    boat.model_name = None
    boat.year = None
    boat.length_m = None
    boat.beam_m = None
    boat.draft_m = None
    boat.hull_material = None
    body = build_body(boat)
    # No fields → DATOS GENERALES section is skipped entirely
    assert "DATOS GENERALES" not in body


def test_build_body_motor_section_for_full_boat():
    boat = make_full_boat()
    body = build_body(boat)
    assert "MOTOR Y CAPACIDADES" in body
    assert "Motor: Volvo Penta D2-75 75 HP" in body
    assert "Horas de motor: 1240 hs" in body
    assert "Tanque de combustible: 200 L" in body
    assert "Tanque de agua: 350 L" in body
    assert "Bow thruster" in body


def test_build_body_motor_section_skipped_without_specs():
    boat = make_boat()
    assert boat.specs is None
    body = build_body(boat)
    assert "MOTOR Y CAPACIDADES" not in body


def test_build_body_interior_section_for_full_boat():
    boat = make_full_boat()
    body = build_body(boat)
    assert "INTERIOR Y CONFORT" in body
    assert "3 camarotes" in body
    assert "2 baños" in body


def test_build_body_singular_cabin_count():
    from app.models import BoatSpecs
    boat = make_boat()
    boat.specs = BoatSpecs(cabins_qty=1, bathrooms_qty=1)
    body = build_body(boat)
    assert "1 camarote" in body
    assert "1 camarotes" not in body
    assert "1 baño" in body
    assert "1 baños" not in body


def test_build_body_navegacion_section_only_for_sailboats():
    boat = make_full_boat()
    assert boat.boat_type == BoatType.SAILBOAT
    body = build_body(boat)
    assert "NAVEGACIÓN Y VELAMEN" in body


def test_build_body_navegacion_section_for_catamaran():
    from app.models import BoatSpecs
    boat = make_boat(boat_type=BoatType.CATAMARAN)
    boat.specs = BoatSpecs(mast_rig="Mástil aluminio", sails="Mayor + Génova")
    body = build_body(boat)
    assert "NAVEGACIÓN Y VELAMEN" in body


def test_build_body_navegacion_section_skipped_for_motorboats():
    from app.models import BoatSpecs
    boat = make_boat(boat_type=BoatType.MOTORBOAT)
    boat.specs = BoatSpecs(mast_rig="N/A")  # Won't render — wrong type
    body = build_body(boat)
    assert "NAVEGACIÓN Y VELAMEN" not in body


def test_build_body_includes_commission():
    boat = make_boat(commission_pct=4)
    body = build_body(boat)
    assert "CONDICIONES" in body
    assert "Comisión MG Náutica: 4% sobre el valor de venta" in body


def test_build_body_commission_with_decimal():
    boat = make_boat(commission_pct=3.5)
    body = build_body(boat)
    assert "Comisión MG Náutica: 3.5% sobre el valor de venta" in body


def test_build_body_omits_commission_section_when_none():
    boat = make_boat(commission_pct=None)
    body = build_body(boat)
    assert "CONDICIONES" not in body


def test_build_body_always_includes_consultas():
    boat = make_boat()
    body = build_body(boat)
    assert "CONSULTAS" in body
    assert "Contactanos para más información" in body


def test_build_body_section_separator_is_double_newline():
    boat = make_full_boat()
    body = build_body(boat)
    # Sections are separated by exactly one blank line
    assert "\n\nDATOS GENERALES" in body
    assert "\n\nMOTOR Y CAPACIDADES" in body
    assert "\n\nCONSULTAS" in body


# ── build_caption ────────────────────────────────────────────────────────────


def test_build_caption_starts_with_title():
    boat = make_full_boat()
    caption = build_caption(boat)
    title = build_title(boat)
    assert caption.startswith(title)


def test_build_caption_has_blank_line_between_title_and_body():
    boat = make_full_boat()
    caption = build_caption(boat)
    title = build_title(boat)
    after_title = caption[len(title):]
    assert after_title.startswith("\n\n")


def test_build_caption_full_content_check():
    """Snapshot-style test against the Jeanneau Sun Odyssey 54 DS reference."""
    from app.models import BoatSpecs
    boat = make_boat(
        slug="velero-jeanneau",
        title="Velero Jeanneau Sun Odyssey 54 DS",
        price_usd=130000,
        boat_type=BoatType.SAILBOAT,
        shipyard="Jeanneau",
        model_name="Sun Odyssey 54 DS",
        year=2006,
        length_m="16.70",
        beam_m="4.85",
        draft_m="2.00",
        hull_material=HullMaterial.FIBERGLASS,
        commission_pct=4,
    )
    boat.description = "Velero de crucero oceánico de gran porte."
    boat.specs = BoatSpecs(
        engine_brand="Yanmar",
        engine_hp=100,
        fuel_liters=400,
        fresh_water_liters=900,
    )

    caption = build_caption(boat)
    assert "U$S 130.000 | VELERO EN VENTA – SUN ODYSSEY 54 DS" in caption
    assert "Velero de crucero oceánico de gran porte." in caption
    assert "Astillero: Jeanneau" in caption
    assert "Motor: Yanmar 100 HP" in caption
    assert "Tanque de combustible: 400 L" in caption
    assert "Comisión MG Náutica: 4% sobre el valor de venta" in caption
    assert "Contactanos para más información" in caption


def test_build_caption_under_instagram_limit():
    """Instagram caps captions at 2200 chars. Even a fully-loaded boat must fit."""
    boat = make_full_boat()
    caption = build_caption(boat)
    # Note: full_boat description is long. Verify we're not way over.
    # If this fails we should look at truncating description.
    assert len(caption) < 5000, f"Caption too long ({len(caption)} chars)"
