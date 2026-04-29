from typing import Optional

from sqlalchemy import or_

from app.factory import db
from app.models import Boat, BoatStatus, BoatType, Flag


class BoatRepository:
    @staticmethod
    def get_by_id(boat_id: int) -> Optional[Boat]:
        return db.session.get(Boat, boat_id)

    @staticmethod
    def get_by_slug(slug: str) -> Optional[Boat]:
        return db.session.query(Boat).filter_by(slug=slug).one_or_none()

    @staticmethod
    def list_available(
        boat_type: Optional[BoatType] = None,
        flag: Optional[Flag] = None,
        min_price_usd: Optional[int] = None,
        max_price_usd: Optional[int] = None,
        min_length_m: Optional[float] = None,
        max_length_m: Optional[float] = None,
        min_draft_m: Optional[float] = None,
        max_draft_m: Optional[float] = None,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        search: Optional[str] = None,
        sort: str = "recent",
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[Boat]:
        query = db.session.query(Boat).filter(Boat.status == BoatStatus.AVAILABLE)

        if boat_type is not None:
            query = query.filter(Boat.boat_type == boat_type)
        if flag is not None:
            query = query.filter(Boat.flag == flag)
        if min_price_usd is not None:
            query = query.filter(Boat.price_usd >= min_price_usd)
        if max_price_usd is not None:
            query = query.filter(Boat.price_usd <= max_price_usd)
        if min_length_m is not None:
            query = query.filter(Boat.length_m >= min_length_m)
        if max_length_m is not None:
            query = query.filter(Boat.length_m <= max_length_m)
        if min_draft_m is not None:
            query = query.filter(Boat.draft_m >= min_draft_m)
        if max_draft_m is not None:
            query = query.filter(Boat.draft_m <= max_draft_m)
        if min_year is not None:
            query = query.filter(Boat.year >= min_year)
        if max_year is not None:
            query = query.filter(Boat.year <= max_year)
        if search:
            term = f"%{search.lower()}%"
            query = query.filter(
                or_(
                    db.func.lower(Boat.title).like(term),
                    db.func.lower(Boat.description).like(term),
                    db.func.lower(Boat.shipyard).like(term),
                    db.func.lower(Boat.model_name).like(term),
                    db.func.lower(Boat.city_location).like(term),
                )
            )

        if sort == "price_asc":
            query = query.order_by(Boat.price_usd.asc())
        elif sort == "price_desc":
            query = query.order_by(Boat.price_usd.desc())
        elif sort == "oldest":
            query = query.order_by(Boat.created_at.asc())
        else:  # "recent" (default)
            query = query.order_by(Boat.featured.desc(), Boat.created_at.desc())

        if offset:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        return query.all()

    @staticmethod
    def list_featured(limit: int = 6) -> list[Boat]:
        return (
            db.session.query(Boat)
            .filter(Boat.status == BoatStatus.AVAILABLE, Boat.featured.is_(True))
            .order_by(Boat.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_available() -> int:
        return (
            db.session.query(Boat)
            .filter(Boat.status == BoatStatus.AVAILABLE)
            .count()
        )

    @staticmethod
    def save(boat: Boat) -> Boat:
        try:
            db.session.add(boat)
            db.session.commit()
            return boat
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def delete(boat: Boat) -> None:
        try:
            db.session.delete(boat)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
