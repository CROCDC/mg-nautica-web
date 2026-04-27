"""Test data factories — create unsaved model instances with sensible defaults."""
from app.models import (
    Accessory,
    AccessoryCategory,
    Boat,
    BoatSpecs,
    BoatStatus,
    BoatType,
    Flag,
    HullMaterial,
    User,
    UserRole,
)


def make_boat(
    slug="velero-test",
    title="Velero Test 35",
    price_usd=45000,
    boat_type=BoatType.SAILBOAT,
    flag=Flag.AR,
    status=BoatStatus.AVAILABLE,
    featured=False,
    **kwargs,
) -> Boat:
    return Boat(
        slug=slug,
        title=title,
        description="Embarcación de prueba.",
        price_usd=price_usd,
        boat_type=boat_type,
        flag=flag,
        status=status,
        featured=featured,
        **kwargs,
    )


def make_full_boat() -> Boat:
    """Bavaria 46 con todos los campos del modelo completados — para screenshots ricos."""
    boat = Boat(
        slug="bavaria-46-full",
        title="Bavaria 46 Cruiser",
        description=(
            "Excepcional velero de crucero listo para zarpar. Bavaria 46 del año 2008 en "
            "perfecto estado, con refit integral realizado en 2023. Equipado con la última "
            "tecnología en electrónica y energía renovable, ideal para circunnavegación o "
            "navegación costera de largo aliento.\n\n"
            "El barco cuenta con tres camarotes dobles, dos baños completos con ducha, saloon "
            "central amplio y cocina totalmente equipada. La instalación eléctrica fue "
            "completamente renovada en 2023 con paneles solares, banco de baterías AGM y "
            "conversor Victron.\n\n"
            "Starlink instalado y funcionando. Lista para larga distancia."
        ),
        price_usd=185000,
        previous_price_usd=210000,
        on_sale=True,
        featured=True,
        boat_type=BoatType.SAILBOAT,
        flag=Flag.UY,
        country_location="Uruguay",
        city_location="Punta del Este",
        zone="Marina de Punta del Este",
        year=2008,
        shipyard="Bavaria Yachtbau",
        model_name="Bavaria 46 Cruiser",
        hull_material=HullMaterial.FIBERGLASS,
        length_m=14.32,
        beam_m=4.43,
        draft_m=1.95,
        displacement_t=9.20,
        commission_pct=3.5,
        last_refit="2023",
        last_careening="2024",
        status=BoatStatus.AVAILABLE,
    )
    boat.specs = BoatSpecs(
        engine_brand="Volvo Penta D2-75",
        engine_hp=75,
        engine_hours=1240,
        propeller="Hélice plegable Gori 3 palas",
        bow_thruster=True,
        fuel_liters=200,
        fresh_water_liters=350,
        sails="Mayor full-batten Elvstrøm · Génova 135% Elvstrøm · Spinnaker asimétrico 120 m²",
        furlers="Harken Mk IV génova · Selden mayor",
        poles="Tangón aluminio 4.5 m",
        bowsprit="Botalón de carbono 1.2 m",
        mast_rig="Mástil aluminio Selden, jarcia de cable 1×19 Dyform inoxidable",
        electronics_plotter="Garmin GPSMap 1242xsv + 942xs",
        electronics_ais="Vesper XB-8000 Clase B",
        electronics_radar="Garmin GMR 18 HD+ 4 kW",
        electronics_wind="Garmin GWS 10",
        electronics_autopilot="B&G Zeus3 + H5000 Hercules",
        electronics_charts="C-MAP MAX-N+ MXTD-D003",
        electronics_vhf="Standard Horizon GX2200",
        electronics_satellite="Iridium GO!",
        electronics_starlink=True,
        batteries_config="3 × AGM 200 Ah servicio · 1 × AGM 100 Ah arranque",
        solar_watts=400,
        inverter_watts=2000,
        chargers="Victron Multiplus 12/3000/120",
        generator="Honda EU2200i 2.2 kVA",
        cabins_qty=3,
        bathrooms_qty=2,
        saloon="Saloon central con mesa abatible para 6 personas",
        galley="Cocina completa con horno, 2 hornallas, fregadero doble",
        fridge="Isotherm Cruise 130 L + frigorífico 30 L",
        tv='Smart TV LG 32" + sonido Bose',
        air_conditioning="Webasto BlueCool S 5000 BTU",
        water_heater="Webasto 10 L + calor motor",
        ground_tackle="Ancora CQR 25 kg + ancora Fortress FX-37",
        chain_meters=60,
        chain_mm=10,
        extra_inventory=(
            "Balsa salvavidas Survitec 6 personas (inspeccionada 2024) · "
            "EPIRB ACR GlobalFix Pro · "
            "Trajes de inmersión Helly Hansen (×2) · "
            "Botiquín offshore completo · "
            "Bengalas homologadas · "
            "Cuerda de vida jackstay · "
            "Radio portátil Standard Horizon HX890 · "
            "Ancla flotante Davis Mk 2 · "
            "Bomba de achique eléctrica Whale 2000 GPH · "
            "Bomba de achique manual de emergencia · "
            "Chalecos salvavidas automáticos Ocean Signal (×6) · "
            "Kayak plegable + remos · "
            "Fuera de borda Honda 2.3 HP (para el tender) · "
            "Eje y hélice de repuesto · "
            "Vela de capa (trinquetilla) · "
            "Kit completo de herramientas y repuestos · "
            "Equipo de buceo completo (×2)"
        ),
    )
    return boat


def make_accessory(
    slug="chaleco-test",
    title="Chaleco Test",
    price_usd=150,
    category=AccessoryCategory.ONBOARD,
    active=True,
) -> Accessory:
    return Accessory(
        slug=slug,
        title=title,
        description="Accesorio de prueba.",
        price_usd=price_usd,
        category=category,
        stock=3,
        active=active,
    )


def make_user(
    email="test@mgnautica.local",
    password="test-password",
    role=UserRole.EDITOR,
    active=True,
) -> User:
    u = User(email=email, name="Test User", role=role, active=active)
    u.set_password(password)
    return u


def make_admin(email="admin@mgnautica.local", password="admin-pass") -> User:
    return make_user(email=email, password=password, role=UserRole.ADMIN)
