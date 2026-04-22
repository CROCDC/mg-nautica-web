from enum import StrEnum


class BoatType(StrEnum):
    SAILBOAT = "sailboat"
    MOTORBOAT = "motorboat"
    CRUISER = "cruiser"
    CATAMARAN = "catamaran"
    YACHT = "yacht"
    WHALER = "whaler"
    OTHER = "other"


class Flag(StrEnum):
    AR = "AR"
    UY = "UY"
    FOREIGN = "FOREIGN"


class HullMaterial(StrEnum):
    FIBERGLASS = "fiberglass"
    WOOD = "wood"
    FERROCEMENT = "ferrocement"
    ALUMINUM = "aluminum"
    STEEL = "steel"
    OTHER = "other"


class BoatStatus(StrEnum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    SOLD = "sold"


class AccessoryCategory(StrEnum):
    ONBOARD = "onboard"
    BOOTS = "boots"
    CLOTHING = "clothing"
    OTHER = "other"


class InquiryChannel(StrEnum):
    WHATSAPP = "whatsapp"
    FORM = "form"
    EMAIL = "email"


class InquiryStatus(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    CLOSED = "closed"


class ProductCondition(StrEnum):
    NEW = "new"
    USED = "used"


class ModerationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class UserRole(StrEnum):
    ADMIN = "admin"
    EDITOR = "editor"
