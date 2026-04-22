from typing import Optional

from app.factory import db
from app.models import BoatType, SaleInquiry


class SaleInquiryRepository:
    @staticmethod
    def create(
        first_name: str,
        last_name: str,
        email: str,
        phone: Optional[str],
        boat_type: BoatType,
        message: Optional[str],
    ) -> SaleInquiry:
        inquiry = SaleInquiry(
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=email.strip().lower(),
            phone=phone.strip() if phone else None,
            boat_type=boat_type,
            message=message.strip() if message else None,
        )
        try:
            db.session.add(inquiry)
            db.session.commit()
            return inquiry
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def list_recent(limit: int = 50) -> list[SaleInquiry]:
        return (
            db.session.query(SaleInquiry)
            .order_by(SaleInquiry.created_at.desc())
            .limit(limit)
            .all()
        )
