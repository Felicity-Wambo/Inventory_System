from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import os

from app.database import Base, engine
from app.routes import register_routers
from app.config import get_settings
from fastapi.templating import Jinja2Templates

settings = get_settings()

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Inventory Management System API",
    version="1.0.0",
)

# Register all API routers
register_routers(app)

# Create required directories
os.makedirs("app/static", exist_ok=True)
os.makedirs("app/templates", exist_ok=True)

# Serve static files
app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)

# Templates
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request}
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME
    }
@app.get(
    "/forgot-password",
    response_class=HTMLResponse
)
def forgot_password_page(
    request: Request
):
    return templates.TemplateResponse(
        "forgot_password.html",
        {
            "request": request
        }
    )


@app.get(
    "/reset-password",
    response_class=HTMLResponse
)
def reset_password_page(
    request: Request
):
    return templates.TemplateResponse(
        "reset_password.html",
        {
            "request": request
        }
    )

@app.get("/items", response_class=HTMLResponse)
def items_page(request: Request):
    return templates.TemplateResponse(
        "items.html",
        {"request": request}
    )

@app.get("/locations", response_class=HTMLResponse)
def locations_page(request: Request):
    return templates.TemplateResponse(
        "locations.html",
        {"request": request}
    )
@app.get("/transactions", response_class=HTMLResponse)
def transactions_page(request: Request):
    return templates.TemplateResponse(
        "transactions.html",
        {"request": request}
    )
@app.get("/stock", response_class=HTMLResponse)
def stock_page(request: Request):
    return templates.TemplateResponse(
        "stock.html",
        {"request": request}
    )
@app.get("/low-stock", response_class=HTMLResponse)
def low_stock_page(request: Request):
    return templates.TemplateResponse(
        "low_stock.html",
        {"request": request}
    )

@app.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request):
    return templates.TemplateResponse(
        "reports.html",
        {"request": request}
    )
@app.get("/products")
def products_page(request: Request):
    return templates.TemplateResponse(
        "products.html",
        {"request": request}
    )
@app.get("/purchases")
def purchases_page(request: Request):
    return templates.TemplateResponse(
        "purchases.html",
        {"request": request}
    )
@app.get("/stock-out", response_class=HTMLResponse)
def stock_out_page(request: Request):
    return templates.TemplateResponse(
        "stock_out.html",
        {"request": request}
    )
@app.get("/stock-out", response_class=HTMLResponse)
def stock_out_page(request: Request):
    return templates.TemplateResponse(
        "stock_out.html",
        {"request": request}
    )
@app.get("/pos", response_class=HTMLResponse)
def pos_page(request: Request):
    return templates.TemplateResponse(
        "pos.html",
        {"request": request}
    )