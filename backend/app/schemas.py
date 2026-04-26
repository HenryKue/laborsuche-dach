from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.enums import ServiceType, Country


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    type: ServiceType
    price_eur: float | None = None


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    street: str
    postal_code: str
    city: str
    country: Country
    latitude: float
    longitude: float
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    self_pay: bool
    source_url: str | None = None
    verified_at: datetime | None = None
    services: list[ServiceOut] = []