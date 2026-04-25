"""One-shot production setup: db upgrade + seed + download images.

Usage:
    docker exec mg-nautica-web python scripts/setup_prod.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from app.factory import db
from app.models import Boat, Accessory, User

with app.app_context():
    print("==> Creating tables...")
    db.create_all()

    print("==> Seeding data...")
    from scripts.seed import seed, sync_photos
    boats, accessories, admin_created = seed()
    print(f"    {boats} new boats ({db.session.query(Boat).count()} total), "
          f"{accessories} new accessories ({db.session.query(Accessory).count()} total)")

    print("==> Syncing photos...")
    synced = sync_photos()
    print(f"    {synced} boats updated with new photos")

    print("==> All done.")
