from fastapi import FastAPI

from . import auth_routes
from . import inventory_routes
from . import transaction as transaction_routes
from . import location_routes
from . import report_routes


def register_routers(app: FastAPI):
    app.include_router(auth_routes.router)
    app.include_router(inventory_routes.router)
    app.include_router(transaction_routes.router)
    app.include_router(location_routes.router)
    app.include_router(report_routes.router)