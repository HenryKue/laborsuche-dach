import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Provider, Service
from app.enums import ServiceType, Country

DATA_FILE = Path(__file__).parent.parent / 'data' / 'providers.json'
def seed_if_empty():
    db: Session = SessionLocal()
    try:
        existing = db.scalar(select(Provider).limit(1))
        if existing is not None:
            print('[seed] DB bereits befüllt, überspringe.')
            return

        if not DATA_FILE.exists():
            print(f'[seed] Keine Datendatei unter {DATA_FILE}, überspringe.')
            return

        raw = json.loads(DATA_FILE.read_text(encoding='utf-8'))
        for entry in raw:
            provider = Provider(
                name=entry['name'],
                street=entry['street'],
                postal_code=entry['postal_code'],
                city=entry['city'],
                country=Country(entry['country']),
                latitude=entry['latitude'],
                longitude=entry['longitude'],
                phone=entry.get('phone'),
                email=entry.get('email'),
                website=entry.get('website'),
                self_pay=entry.get('self_pay', True),
                source_url=entry.get('source_url'),
                verified_at=datetime.fromisoformat(entry['verified_at']) if entry.get('verified_at') else None,
            )
            for svc in entry.get('services', []):
                provider.services.append(Service(
                    type=ServiceType(svc['type']),
                    price_eur=svc.get('price_eur'),
                ))
            db.add(provider)

        db.commit()
        print(f'[seed] {len(raw)} Provider eingefügt.')
    finally:
        db.close()