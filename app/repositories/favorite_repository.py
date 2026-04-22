from typing import Optional

from app.factory import db
from app.models import Favorite


class FavoriteRepository:
    @staticmethod
    def get(listed_object_id: int, session_id: str) -> Optional[Favorite]:
        return (
            db.session.query(Favorite)
            .filter_by(listed_object_id=listed_object_id, session_id=session_id)
            .one_or_none()
        )

    @staticmethod
    def add(listed_object_id: int, session_id: str) -> Favorite:
        existing = FavoriteRepository.get(listed_object_id, session_id)
        if existing is not None:
            return existing
        favorite = Favorite(listed_object_id=listed_object_id, session_id=session_id)
        try:
            db.session.add(favorite)
            db.session.commit()
            return favorite
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def remove(listed_object_id: int, session_id: str) -> bool:
        existing = FavoriteRepository.get(listed_object_id, session_id)
        if existing is None:
            return False
        try:
            db.session.delete(existing)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def list_for_session(session_id: str) -> list[Favorite]:
        return (
            db.session.query(Favorite)
            .filter_by(session_id=session_id)
            .order_by(Favorite.created_at.desc())
            .all()
        )
