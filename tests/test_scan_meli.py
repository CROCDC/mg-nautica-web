"""Tests for scripts/scan_meli.py.

Covers:
- _normalize(): emoji stripping, accent removal, noise filtering, bigrams
- _f1(): perfect match, partial, disjoint, empty sets
- match_listings(): greedy 1-to-1, correct winner, unmatched listings
- apply_matches(): DB writes, skips already-linked, skips low score, count
"""
from scripts.scan_meli import _f1, _normalize, apply_matches, match_listings
from tests.factories import make_boat, make_accessory


# ── helpers ────────────────────────────────────────────────────────────────────

def _listing(title: str, meli_id: str = "MLA1234567", status: str = "active") -> dict:
    return {
        "title": title,
        "meli_id": meli_id,
        "meli_url": f"https://vehiculo.mercadolibre.com.ar/{meli_id}",
        "status": status,
        "price_raw": "45.000",
    }


# ── _normalize ────────────────────────────────────────────────────────────────

class TestNormalize:
    def test_strips_emojis(self):
        tokens = _normalize("⛵ VELERO PANDORA 34 🇦🇷")
        assert "velero" in tokens
        assert "pandora" in tokens
        assert "34" in tokens
        assert all(t.isascii() for t in tokens)

    def test_removes_accents(self):
        tokens = _normalize("Velero Clásico Ferrocemento")
        assert "clasico" in tokens
        assert "ferrocemento" in tokens
        assert "Clásico" not in tokens

    def test_filters_noise_words(self):
        tokens = _normalize("Velero Pandora 34 En Venta Oportunidad")
        assert "en" not in tokens
        assert "venta" not in tokens
        assert "oportunidad" not in tokens
        assert "pandora" in tokens

    def test_generates_unigram_bigrams(self):
        tokens = _normalize("Velero Pandora 34")
        assert "velero" in tokens
        assert "pandora" in tokens
        # at least one bigram with underscore
        assert any("_" in t for t in tokens)

    def test_strips_bullet_and_reserved(self):
        tokens = _normalize("●RESERVADO | VELERO PLENAMAR 23")
        assert "plenamar" in tokens
        assert "23" in tokens
        assert "reservado" in tokens  # not a noise word, kept

    def test_handles_empty_string(self):
        assert _normalize("") == set()

    def test_normalizes_real_db_title(self):
        tokens = _normalize("VELERO CLÁSICO FERROCEMENTO | CON ORZA | BANDERA 🇦🇷")
        assert "velero" in tokens
        assert "clasico" in tokens
        assert "ferrocemento" in tokens
        assert "bandera" not in tokens   # noise word
        assert "orza" not in tokens      # noise word

    def test_normalizes_real_ml_title(self):
        tokens = _normalize("Velero Clásico Ferrocemento | Con Orza")
        assert "velero" in tokens
        assert "clasico" in tokens
        assert "ferrocemento" in tokens
        assert "con" not in tokens
        assert "orza" not in tokens


# ── _f1 ───────────────────────────────────────────────────────────────────────

class TestF1:
    def test_identical_sets_score_one(self):
        s = {"velero", "pandora", "34"}
        assert _f1(s, s) == 1.0

    def test_disjoint_sets_score_zero(self):
        assert _f1({"velero", "pandora"}, {"lancha", "quicksilver"}) == 0.0

    def test_partial_overlap_between_zero_and_one(self):
        score = _f1({"velero", "pandora", "34"}, {"velero", "pandora", "23"})
        assert 0 < score < 1.0

    def test_empty_first_arg_is_zero(self):
        assert _f1(set(), {"velero", "pandora"}) == 0.0

    def test_empty_second_arg_is_zero(self):
        assert _f1({"velero", "pandora"}, set()) == 0.0

    def test_subset_scores_less_than_identical(self):
        full = {"velero", "pandora", "34"}
        subset = {"velero", "pandora"}
        assert _f1(subset, full) < 1.0

    def test_larger_set_penalty(self):
        # Adding irrelevant tokens to the ML title reduces precision
        exact = _f1({"velero", "pandora", "34"}, {"velero", "pandora", "34"})
        noisy = _f1(
            {"velero", "pandora", "34", "impecable", "motor", "a"},
            {"velero", "pandora", "34"},
        )
        assert noisy < exact


# ── match_listings ────────────────────────────────────────────────────────────

class TestMatchListings:
    def test_exact_title_match(self):
        boat = make_boat(slug="pandora-34", title="VELERO PANDORA 34")
        matches = match_listings([_listing("Velero Pandora 34", "MLA1111")], [boat])
        assert len(matches) == 1
        assert matches[0]["boat"] is boat
        assert matches[0]["score"] == 1.0

    def test_noisy_ml_title_still_matches(self):
        boat = make_boat(slug="pandora-34", title="VELERO PANDORA 34")
        matches = match_listings(
            [_listing("Velero Pandora 34 - Impecable | En Venta", "MLA1111")], [boat]
        )
        assert matches[0]["boat"] is boat
        assert matches[0]["score"] >= 0.8

    def test_greedy_one_to_one_second_listing_gets_none(self):
        """Two listings for the same boat: only the best-scoring one wins."""
        boat = make_boat(slug="pandora-34", title="VELERO PANDORA 34")
        matches = match_listings(
            [
                _listing("Velero Pandora 34 Impecable", "MLA1111"),
                _listing("Pandora 34 En Venta", "MLA2222"),
            ],
            [boat],
        )
        assigned = [m for m in matches if m["boat"] is not None]
        assert len(assigned) == 1

    def test_two_similar_boats_split_between_two_listings(self):
        """Two Miura 25 listings → two different DB boats (greedy 1-to-1)."""
        b1 = make_boat(slug="miura-a", title="VELERO MIURA 25 - A MEJORAR")
        b2 = make_boat(slug="miura-b", title="VELERO MIURA 25 DOMINANTE II")
        matches = match_listings(
            [
                _listing("Velero Miura 25 (oportunidad)", "MLA1111"),
                _listing("Velero Miura 25 | En Venta", "MLA2222"),
            ],
            [b1, b2],
        )
        assigned_boats = {m["boat"].slug for m in matches if m["boat"]}
        assert assigned_boats == {"miura-a", "miura-b"}

    def test_no_boats_returns_no_match(self):
        matches = match_listings([_listing("Velero Pandora 34", "MLA1111")], [])
        assert matches[0]["boat"] is None
        assert matches[0]["score"] == 0.0

    def test_unmatched_listing_always_present_in_results(self):
        """Every listing appears in the result, even those with no good match."""
        boat = make_boat(slug="lancha", title="LANCHA RÁPIDA")
        matches = match_listings([_listing("Velero Pandora 34", "MLA1111")], [boat])
        assert len(matches) == 1
        assert matches[0]["listing"]["meli_id"] == "MLA1111"

    def test_multiple_boats_picks_best(self):
        b_pandora = make_boat(slug="pandora-34", title="VELERO PANDORA 34")
        b_pandora23 = make_boat(slug="pandora-23", title="VELERO PANDORA 23")
        b_miura = make_boat(slug="miura", title="VELERO MIURA 25")
        matches = match_listings(
            [_listing("Velero Pandora 34", "MLA1111")],
            [b_pandora, b_pandora23, b_miura],
        )
        assert matches[0]["boat"].slug == "pandora-34"

    def test_result_contains_all_listings(self):
        b1 = make_boat(slug="b1", title="VELERO PANDORA 34")
        b2 = make_boat(slug="b2", title="VELERO MIURA 25")
        listings = [
            _listing("Velero Pandora 34", "MLA1111"),
            _listing("Velero Miura 25", "MLA2222"),
            _listing("Barco Inexistente XYZ", "MLA3333"),
        ]
        matches = match_listings(listings, [b1, b2])
        result_ids = {m["listing"]["meli_id"] for m in matches}
        assert result_ids == {"MLA1111", "MLA2222", "MLA3333"}


# ── apply_matches ─────────────────────────────────────────────────────────────

class TestApplyMatches:
    def test_saves_meli_fields_to_db(self, db):
        boat = make_boat(slug="pandora-34", title="VELERO PANDORA 34")
        db.session.add(boat)
        db.session.commit()

        listing = _listing("Velero Pandora 34", "MLA9999", status="active")
        updated = apply_matches(
            [{"listing": listing, "boat": boat, "score": 1.0}], min_score=0.5
        )

        db.session.refresh(boat)
        assert updated == 1
        assert boat.meli_mla_item_id == "MLA9999"
        assert "MLA-9999" in boat.meli_mla_permalink or "MLA9999" in boat.meli_mla_permalink
        assert boat.meli_mla_status == "active"
        assert boat.meli_mla_synced_at is not None

    def test_skips_already_linked_boat(self, db):
        boat = make_boat(slug="pandora-34", title="VELERO PANDORA 34")
        boat.meli_mla_item_id = "MLA0001"
        db.session.add(boat)
        db.session.commit()

        updated = apply_matches(
            [{"listing": _listing("Velero Pandora 34", "MLA9999"), "boat": boat, "score": 1.0}],
            min_score=0.5,
        )

        db.session.refresh(boat)
        assert updated == 0
        assert boat.meli_mla_item_id == "MLA0001"  # unchanged

    def test_skips_score_below_threshold(self, db):
        boat = make_boat(slug="pandora-34", title="VELERO PANDORA 34")
        db.session.add(boat)
        db.session.commit()

        updated = apply_matches(
            [{"listing": _listing("Velero Pandora 34", "MLA9999"), "boat": boat, "score": 0.3}],
            min_score=0.5,
        )

        db.session.refresh(boat)
        assert updated == 0
        assert boat.meli_mla_item_id is None

    def test_skips_none_boat(self, db):
        updated = apply_matches(
            [{"listing": _listing("Barco Raro", "MLA9999"), "boat": None, "score": 0.0}],
            min_score=0.5,
        )
        assert updated == 0

    def test_returns_correct_count(self, db):
        boats = [make_boat(slug=f"b{i}", title=f"VELERO TIPO {i}") for i in range(4)]
        for b in boats:
            db.session.add(b)
        db.session.commit()

        matches = [
            {"listing": _listing(f"Velero Tipo {i}", f"MLA{9000 + i}"), "boat": b, "score": 0.9}
            for i, b in enumerate(boats)
        ]
        updated = apply_matches(matches, min_score=0.5)
        assert updated == 4

    def test_applies_min_score_exactly(self, db):
        boat = make_boat(slug="pandora-34", title="VELERO PANDORA 34")
        db.session.add(boat)
        db.session.commit()

        # score == min_score should be accepted
        updated = apply_matches(
            [{"listing": _listing("Velero Pandora 34", "MLA9999"), "boat": boat, "score": 0.5}],
            min_score=0.5,
        )
        assert updated == 1

    def test_paused_status_saved(self, db):
        boat = make_boat(slug="pandora-34", title="VELERO PANDORA 34")
        db.session.add(boat)
        db.session.commit()

        apply_matches(
            [{"listing": _listing("Velero Pandora 34", "MLA9999", status="paused"),
              "boat": boat, "score": 1.0}],
            min_score=0.5,
        )
        db.session.refresh(boat)
        assert boat.meli_mla_status == "paused"


# ── real-world title pairs ────────────────────────────────────────────────────

class TestRealWorldPairs:
    """Spot-checks that the actual mgnautica listings match the right DB titles."""

    PAIRS = [
        ("Velero Clásico Ferrocemento | Con Orza",
         "VELERO CLÁSICO FERROCEMENTO | CON ORZA | BANDERA 🇦🇷"),
        ("Catamaran Nautitech 46 Open | Piriapolis | En Venta",
         "CATAMARAN NAUTITECH 46 OPEN | 📍Piriapolis 🇺🇾 | En Venta"),
        ("Jeanneau Sun Odyssey 40 | En Panamá",
         "⛵ JEANNEAU SUN ODYSSEY 40 | 📍Panama"),
        ("Velero Cp 26 | Versión Crucero | Motor Interno",
         "VELERO CP 26 (CRUCERO)"),
        ("Velero Dufour 425 | Grand Large | 2008 Piriapolis",
         "DUFOUR 425 GRAND LARGE | 2008 | EN VENTA🇺🇾"),
        ("Motovelero Clasico Doble Proa | En Venta",
         "VELERO CLÁSICO DOBLE PROA"),
        ("Ballenera Clásica De Madera | 1949 | En Venta",
         "BALLENERA CLÁSICA DE MADERA🇦🇷 | 1949"),
        ("Venta Trento 250",
         "CRUCERO TRENTO 250"),
    ]

    def test_each_pair_scores_above_threshold(self):
        for ml_title, db_title in self.PAIRS:
            score = _f1(_normalize(ml_title), _normalize(db_title))
            assert score >= 0.5, (
                f"Score {score:.2f} too low for:\n"
                f"  ML: {ml_title!r}\n"
                f"  DB: {db_title!r}"
            )

    def test_each_pair_beats_decoy(self):
        """Each ML title must score higher against its real match than a random decoy."""
        decoy_db = "LANCHA RÁPIDA 505 MOTOR FUERA DE BORDA"
        for ml_title, db_title in self.PAIRS:
            real_score = _f1(_normalize(ml_title), _normalize(db_title))
            decoy_score = _f1(_normalize(ml_title), _normalize(decoy_db))
            assert real_score > decoy_score, (
                f"Decoy won for ML title: {ml_title!r}\n"
                f"  real={real_score:.2f} vs decoy={decoy_score:.2f}"
            )
