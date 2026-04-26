from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from app.database import Base, engine, get_db
from app import models
from app.schemas import ProviderOut
from app.seed import seed_if_empty

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_if_empty()
    yield

app = FastAPI(title='Laborsuche DACH', lifespan=lifespan)

@app.get('/api/health')
def health():
    return {'status': 'ok'}

@app.get('/api/providers', response_model=list[ProviderOut])
def list_providers(db: Session = Depends(get_db)):
    stmt = select(models.Provider).options(selectinload(models.Provider.services))
    return db.scalars(stmt).all()

app.mount("/", StaticFiles(directory="frontend_dist", html=True), name="frontend")