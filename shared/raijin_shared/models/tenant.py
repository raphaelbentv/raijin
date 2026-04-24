from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from raijin_shared.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Tenant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="GR")
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    default_locale: Mapped[str] = mapped_column(String(10), nullable=False, default="fr")
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
