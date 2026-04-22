"""Test data factories — create unsaved model instances with sensible defaults."""
from app.models import (
    Accessory,
    AccessoryCategory,
    Boat,
    BoatStatus,
    BoatType,
    Flag,
    User,
    UserRole,
)


def make_boat(
    slug="velero-test",
    title="Velero Test 35",
    price_usd=45000,
    boat_type=BoatType.SAILBOAT,
    flag=Flag.AR,
    status=BoatStatus.AVAILABLE,
    featured=False,
    **kwargs,
) -> Boat:
    return Boat(
        slug=slug,
        title=title,
        description="Embarcación de prueba.",
        price_usd=price_usd,
        boat_type=boat_type,
        flag=flag,
        status=status,
        featured=featured,
        **kwargs,
    )


def make_accessory(
    slug="chaleco-test",
    title="Chaleco Test",
    price_usd=150,
    category=AccessoryCategory.ONBOARD,
    active=True,
) -> Accessory:
    return Accessory(
        slug=slug,
        title=title,
        description="Accesorio de prueba.",
        price_usd=price_usd,
        category=category,
        stock=3,
        active=active,
    )


def make_user(
    email="test@mgnautica.local",
    password="test-password",
    role=UserRole.EDITOR,
    active=True,
) -> User:
    u = User(email=email, name="Test User", role=role, active=active)
    u.set_password(password)
    return u


def make_admin(email="admin@mgnautica.local", password="admin-pass") -> User:
    return make_user(email=email, password=password, role=UserRole.ADMIN)
