from datetime import datetime
from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import ServiceType, Country

class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    street: Mapped[str] = mapped_column(String(200))
    postal_code: Mapped[str] = mapped_column(String(10))
    city: Mapped[str] = mapped_column(String(100))
    country: Mapped[Country]
    latitude: Mapped[float]
    longitude: Mapped[float]
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(200))
    website: Mapped[str | None] = mapped_column(String(500))
    self_pay: Mapped[bool] = mapped_column(default=True)
    source_url: Mapped[str | None] = mapped_column(String(500))
    verified_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    services: Mapped[list["Service"]] = relationship(
        back_populates="provider",
        cascade="all, delete-orphan"
    )

class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    type: Mapped[ServiceType]
    price_eur: Mapped[float | None]

    provider: Mapped[Provider] = relationship(back_populates="services")