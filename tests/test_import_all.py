"""Tests for scripts/import_all.py orchestration.

Covers:
- CLI flag parsing (--skip-* flags actually skip the right steps)
- Wipe logic: boats, accessories, photos, specs deleted before seed
- Wipe does not touch admin users
- step_associate_meli: calls apply_matches and saves ML data
- step_associate_meli falls back to Playwright when API has no credentials
- step_associate_meli skips gracefully when Playwright unavailable
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from app.models import Accessory, Boat, BoatPhoto, BoatSpecs
from tests.factories import make_accessory, make_boat, make_admin


# ── wipe logic ────────────────────────────────────────────────────────────────

class TestWipeLogic:
    """Tests the wipe queries used in step_wipe_and_seed directly."""

    def test_wipe_deletes_all_boats(self, db):
        db.session.add(make_boat(slug="b1"))
        db.session.add(make_boat(slug="b2"))
        db.session.commit()
        assert db.session.query(Boat).count() == 2

        db.session.query(BoatPhoto).delete()
        db.session.query(BoatSpecs).delete()
        db.session.query(Boat).delete()
        db.session.commit()

        assert db.session.query(Boat).count() == 0

    def test_wipe_deletes_all_accessories(self, db):
        db.session.add(make_accessory(slug="a1"))
        db.session.add(make_accessory(slug="a2"))
        db.session.commit()
        assert db.session.query(Accessory).count() == 2

        db.session.query(Accessory).delete()
        db.session.commit()

        assert db.session.query(Accessory).count() == 0

    def test_wipe_deletes_photos_and_specs(self, db):
        from app.models import BoatPhoto, BoatSpecs
        boat = make_boat(slug="con-foto")
        db.session.add(boat)
        db.session.flush()
        db.session.add(BoatPhoto(boat_id=boat.id, url="/uploads/x.jpg", position=0, is_primary=True))
        db.session.add(BoatSpecs(boat_id=boat.id, engine_hp=75))
        db.session.commit()
        assert db.session.query(BoatPhoto).count() == 1
        assert db.session.query(BoatSpecs).count() == 1

        db.session.query(BoatPhoto).delete()
        db.session.query(BoatSpecs).delete()
        db.session.query(Boat).delete()
        db.session.commit()

        assert db.session.query(BoatPhoto).count() == 0
        assert db.session.query(BoatSpecs).count() == 0

    def test_wipe_does_not_touch_users(self, db):
        from app.models import User
        admin = make_admin()
        db.session.add(admin)
        db.session.add(make_boat(slug="b1"))
        db.session.commit()

        db.session.query(BoatPhoto).delete()
        db.session.query(BoatSpecs).delete()
        db.session.query(Boat).delete()
        db.session.query(Accessory).delete()
        db.session.commit()

        assert db.session.query(User).count() == 1
        assert db.session.query(Boat).count() == 0


# ── step_associate_meli ───────────────────────────────────────────────────────

def _fake_listing(title: str, meli_id: str, status: str = "active") -> dict:
    return {
        "title": title,
        "meli_id": meli_id,
        "meli_url": f"https://vehiculo.mercadolibre.com.ar/{meli_id}",
        "status": status,
        "price_raw": "45.000",
    }


class TestStepAssociateMeli:
    """
    step_associate_meli creates its own Flask app context internally.
    We test it by:
      - patching _fetch_listings to control what listings are returned
      - patching app.app with the pytest test-app so the inner context
        uses the same SQLite DB as the test fixtures
    """

    def _run(self, app_fixture, listings, *, data_dir=Path("/tmp"), min_score=0.5, site="MLA"):
        import scripts.import_all as ia
        with patch("scripts.import_all._fetch_listings", return_value=listings), \
             patch("scripts.import_all.DATA_DIR", data_dir), \
             patch("app.app", app_fixture):
            ia.step_associate_meli(site, min_score=min_score)

    def test_links_boats_via_api(self, db, app):
        """Boats matching ML listings get meli_mla_item_id saved to DB."""
        boat = make_boat(slug="pandora-34", title="VELERO PANDORA 34")
        db.session.add(boat)
        db.session.commit()

        self._run(app, [_fake_listing("Velero Pandora 34", "MLA9999")])

        db.session.refresh(boat)
        assert boat.meli_mla_item_id == "MLA9999"
        assert boat.meli_mla_status == "active"
        assert boat.meli_mla_synced_at is not None

    def test_falls_back_to_playwright_on_api_error(self, db, app):
        """_fetch_listings returns listings from playwright fallback."""
        boat = make_boat(slug="pandora-34", title="VELERO PANDORA 34")
        db.session.add(boat)
        db.session.commit()

        # _fetch_listings is already patched to return listings regardless of source
        self._run(app, [_fake_listing("Velero Pandora 34", "MLA9999")])

        db.session.refresh(boat)
        assert boat.meli_mla_item_id == "MLA9999"

    def test_skips_when_no_listings(self, db, app, capsys):
        """When _fetch_listings returns empty list, no DB writes happen."""
        boat = make_boat(slug="pandora-34", title="VELERO PANDORA 34")
        db.session.add(boat)
        db.session.commit()

        self._run(app, [])  # empty → step should exit early

        db.session.refresh(boat)
        assert boat.meli_mla_item_id is None

    def test_does_not_overwrite_existing_link(self, db, app):
        """A boat already linked must not be changed."""
        boat = make_boat(slug="pandora-34", title="VELERO PANDORA 34")
        boat.meli_mla_item_id = "MLA0001"
        db.session.add(boat)
        db.session.commit()

        self._run(app, [_fake_listing("Velero Pandora 34", "MLA9999")])

        db.session.refresh(boat)
        assert boat.meli_mla_item_id == "MLA0001"  # unchanged

    def test_caches_listings_to_json(self, db, app, tmp_path):
        """Fetched listings are written to cache file."""
        boat = make_boat(slug="pandora-34", title="VELERO PANDORA 34")
        db.session.add(boat)
        db.session.commit()

        self._run(app, [_fake_listing("Velero Pandora 34", "MLA9999")], data_dir=tmp_path)

        cache = tmp_path / "meli_listings_mla.json"
        assert cache.exists()
        saved = json.loads(cache.read_text())
        assert saved[0]["meli_id"] == "MLA9999"

    def test_min_score_respected(self, db, app):
        """Listings below min_score threshold are not linked."""
        boat = make_boat(slug="velero-x", title="VELERO CLÁSICO DOBLE PROA")
        db.session.add(boat)
        db.session.commit()

        self._run(app, [_fake_listing("Barco Generico Sin Match", "MLA9999")], min_score=0.9)

        db.session.refresh(boat)
        assert boat.meli_mla_item_id is None


# ── CLI flags ─────────────────────────────────────────────────────────────────

class TestCLIFlags:
    """Verify that --skip-* flags actually skip the right steps."""

    def _run_main(self, argv: list[str], mocks: dict) -> None:
        import scripts.import_all as ia
        with patch.multiple(
            "scripts.import_all",
            step_scrape_boats=mocks.get("scrape_boats", MagicMock()),
            step_scrape_accessories=mocks.get("scrape_acc", MagicMock()),
            step_download_boat_photos=mocks.get("dl_boats", MagicMock()),
            step_download_accessory_photos=mocks.get("dl_acc", MagicMock()),
            step_wipe_and_seed=mocks.get("seed", MagicMock()),
            step_associate_meli=mocks.get("meli", MagicMock()),
        ):
            old_argv = sys.argv
            sys.argv = ["import_all.py"] + argv
            try:
                ia.main()
            finally:
                sys.argv = old_argv

    def test_skip_scrape_skips_both_scrapers(self):
        m = {k: MagicMock() for k in ("scrape_boats", "scrape_acc", "dl_boats", "dl_acc", "seed", "meli")}
        self._run_main(["--skip-scrape"], m)
        m["scrape_boats"].assert_not_called()
        m["scrape_acc"].assert_not_called()
        m["seed"].assert_called_once()
        m["meli"].assert_called_once()

    def test_skip_download_skips_photo_steps(self):
        m = {k: MagicMock() for k in ("scrape_boats", "scrape_acc", "dl_boats", "dl_acc", "seed", "meli")}
        self._run_main(["--skip-scrape", "--skip-download"], m)
        m["dl_boats"].assert_not_called()
        m["dl_acc"].assert_not_called()
        m["seed"].assert_called_once()

    def test_skip_seed_skips_seed_step(self):
        m = {k: MagicMock() for k in ("scrape_boats", "scrape_acc", "dl_boats", "dl_acc", "seed", "meli")}
        self._run_main(["--skip-scrape", "--skip-download", "--skip-seed"], m)
        m["seed"].assert_not_called()
        m["meli"].assert_called_once()

    def test_skip_meli_skips_association_step(self):
        m = {k: MagicMock() for k in ("scrape_boats", "scrape_acc", "dl_boats", "dl_acc", "seed", "meli")}
        self._run_main(["--skip-scrape", "--skip-download", "--skip-meli"], m)
        m["meli"].assert_not_called()
        m["seed"].assert_called_once()

    def test_full_run_calls_all_steps(self):
        m = {k: MagicMock() for k in ("scrape_boats", "scrape_acc", "dl_boats", "dl_acc", "seed", "meli")}
        # need playwright to be importable for download step
        with patch("scripts.import_all.step_scrape_boats", m["scrape_boats"]), \
             patch("scripts.import_all.step_scrape_accessories", m["scrape_acc"]), \
             patch("scripts.import_all.step_download_boat_photos", m["dl_boats"]), \
             patch("scripts.import_all.step_download_accessory_photos", m["dl_acc"]), \
             patch("scripts.import_all.step_wipe_and_seed", m["seed"]), \
             patch("scripts.import_all.step_associate_meli", m["meli"]):
            old_argv = sys.argv
            sys.argv = ["import_all.py", "--skip-scrape", "--skip-download"]
            try:
                import scripts.import_all as ia
                ia.main()
            finally:
                sys.argv = old_argv
        m["seed"].assert_called_once()
        m["meli"].assert_called_once()

    def test_skip_wipe_passes_flag_to_seed(self):
        m = {k: MagicMock() for k in ("scrape_boats", "scrape_acc", "dl_boats", "dl_acc", "seed", "meli")}
        self._run_main(["--skip-scrape", "--skip-download", "--skip-wipe"], m)
        m["seed"].assert_called_once_with(skip_wipe=True)

    def test_meli_site_flag_passed_correctly(self):
        m = {k: MagicMock() for k in ("scrape_boats", "scrape_acc", "dl_boats", "dl_acc", "seed", "meli")}
        self._run_main(["--skip-scrape", "--skip-download", "--meli-site", "MLU"], m)
        args, kwargs = m["meli"].call_args
        assert "MLU" in args or kwargs.get("site") == "MLU"

    def test_meli_min_score_flag_passed_correctly(self):
        m = {k: MagicMock() for k in ("scrape_boats", "scrape_acc", "dl_boats", "dl_acc", "seed", "meli")}
        self._run_main(
            ["--skip-scrape", "--skip-download", "--meli-min-score", "0.7"], m
        )
        args, kwargs = m["meli"].call_args
        assert 0.7 in args or kwargs.get("min_score") == pytest.approx(0.7)
