# app/__init__.py
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer
import os

from app.database import Base, engine
from app.routes import (
    auth_routes, inventory_routes, transaction_routes,
    location_routes, report_routes
)
from app.config import get_settings

settings = get_settings()

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_NAME)

# Include routers
app.include_router(auth_routes.router)
app.include_router(inventory_routes.router)
app.include_router(transaction_routes.router)
app.include_router(location_routes.router)
app.include_router(report_routes.router)

# Static files
os.makedirs("app/static", exist_ok=True)
os.makedirs("app/templates", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}