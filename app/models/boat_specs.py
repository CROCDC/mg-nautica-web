from typing import Any

from app.factory import db


class BoatSpecs(db.Model):
    __tablename__ = "boat_specs"

    id = db.Column(db.Integer, primary_key=True)
    boat_id = db.Column(
        db.Integer, db.ForeignKey("boats.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    engine_brand = db.Column(db.String(120), nullable=True)
    engine_hp = db.Column(db.Integer, nullable=True)
    engine_hours = db.Column(db.Integer, nullable=True)
    propeller = db.Column(db.String(160), nullable=True)
    bow_thruster = db.Column(db.Boolean, default=False, nullable=False)
    fuel_liters = db.Column(db.Integer, nullable=True)
    fresh_water_liters = db.Column(db.Integer, nullable=True)

    sails = db.Column(db.Text, nullable=True)
    furlers = db.Column(db.String(200), nullable=True)
    poles = db.Column(db.String(200), nullable=True)
    bowsprit = db.Column(db.String(120), nullable=True)
    mast_rig = db.Column(db.String(200), nullable=True)

    electronics_plotter = db.Column(db.String(200), nullable=True)
    electronics_ais = db.Column(db.String(120), nullable=True)
    electronics_radar = db.Column(db.String(120), nullable=True)
    electronics_wind = db.Column(db.String(120), nullable=True)
    electronics_autopilot = db.Column(db.String(120), nullable=True)
    electronics_charts = db.Column(db.String(120), nullable=True)
    electronics_vhf = db.Column(db.String(120), nullable=True)
    electronics_satellite = db.Column(db.String(120), nullable=True)
    electronics_starlink = db.Column(db.Boolean, default=False, nullable=False)

    batteries_config = db.Column(db.Text, nullable=True)
    solar_watts = db.Column(db.Integer, nullable=True)
    inverter_watts = db.Column(db.Integer, nullable=True)
    chargers = db.Column(db.String(200), nullable=True)
    generator = db.Column(db.String(200), nullable=True)

    cabins_qty = db.Column(db.Integer, nullable=True)
    bathrooms_qty = db.Column(db.Integer, nullable=True)
    saloon = db.Column(db.String(200), nullable=True)
    galley = db.Column(db.String(200), nullable=True)
    fridge = db.Column(db.String(200), nullable=True)
    tv = db.Column(db.String(120), nullable=True)
    air_conditioning = db.Column(db.String(120), nullable=True)
    water_heater = db.Column(db.String(120), nullable=True)

    ground_tackle = db.Column(db.Text, nullable=True)
    chain_meters = db.Column(db.Integer, nullable=True)
    chain_mm = db.Column(db.Integer, nullable=True)

    extra_inventory = db.Column(db.Text, nullable=True)

    boat = db.relationship("Boat", back_populates="specs")

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": {
                "brand": self.engine_brand,
                "hp": self.engine_hp,
                "hours": self.engine_hours,
                "propeller": self.propeller,
                "bow_thruster": self.bow_thruster,
                "fuel_liters": self.fuel_liters,
                "fresh_water_liters": self.fresh_water_liters,
            },
            "sails": {
                "sails": self.sails,
                "furlers": self.furlers,
                "poles": self.poles,
                "bowsprit": self.bowsprit,
                "mast_rig": self.mast_rig,
            },
            "electronics": {
                "plotter": self.electronics_plotter,
                "ais": self.electronics_ais,
                "radar": self.electronics_radar,
                "wind": self.electronics_wind,
                "autopilot": self.electronics_autopilot,
                "charts": self.electronics_charts,
                "vhf": self.electronics_vhf,
                "satellite": self.electronics_satellite,
                "starlink": self.electronics_starlink,
            },
            "power": {
                "batteries_config": self.batteries_config,
                "solar_watts": self.solar_watts,
                "inverter_watts": self.inverter_watts,
                "chargers": self.chargers,
                "generator": self.generator,
            },
            "living": {
                "cabins_qty": self.cabins_qty,
                "bathrooms_qty": self.bathrooms_qty,
                "saloon": self.saloon,
                "galley": self.galley,
                "fridge": self.fridge,
                "tv": self.tv,
                "air_conditioning": self.air_conditioning,
                "water_heater": self.water_heater,
            },
            "ground_tackle": {
                "description": self.ground_tackle,
                "chain_meters": self.chain_meters,
                "chain_mm": self.chain_mm,
            },
            "extra_inventory": self.extra_inventory,
        }
