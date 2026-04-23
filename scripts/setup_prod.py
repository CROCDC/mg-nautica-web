"""One-shot production setup: db upgrade + seed + download images.

Usage:
    docker exec mg-nautica-web python scripts/setup_prod.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask_migrate import upgrade

from app import app
from app.factory import db
from app.models import Boat, Accessory, User

with app.app_context():
    print("==> Running DB migrations...")
    upgrade()

    print("==> Seeding data...")
    from scripts.seed import seed
    boats, accessories, admin_created = seed()
    print(f"    {boats} new boats ({db.session.query(Boat).count()} total), "
          f"{accessories} new accessories ({db.session.query(Accessory).count()} total)")

    print("==> Downloading images...")
    import scripts.download_images as dl
    dl.main()

    print("==> All done.")
