from typing import Optional

from app.factory import db
from app.models import Accessory, AccessoryCategory


class AccessoryRepository:
    @staticmethod
    def get_by_id(accessory_id: int) -> Optional[Accessory]:
        return db.session.get(Accessory, accessory_id)

    @staticmethod
    def get_by_slug(slug: str) -> Optional[Accessory]:
        return db.session.query(Accessory).filter_by(slug=slug).one_or_none()

    @staticmethod
    def list_active(
        category: Optional[AccessoryCategory] = None,
    ) -> list[Accessory]:
        query = db.session.query(Accessory).filter(Accessory.active.is_(True))
        if category is not None:
            query = query.filter(Accessory.category == category)
        return query.order_by(Accessory.created_at.desc()).all()

    @staticmethod
    def save(accessory: Accessory) -> Accessory:
        try:
            db.session.add(accessory)
            db.session.commit()
            return accessory
        except Exception:
            db.session.rollback()
            raise
