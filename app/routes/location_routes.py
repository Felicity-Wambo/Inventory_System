# app/routes/location_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from app.database import get_db
from app.models import Location, InventoryItem, User, UserRole
from app.auth import get_current_user, require_role

router = APIRouter(prefix="/api/locations", tags=["locations"])


class LocationCreate(BaseModel):
    code: str
    name: str
    address: str = ""


@router.get("")
def list_locations(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    return [
        {"id": l.id, "code": l.code, "name": l.name,
         "address": l.address, "is_active": l.is_active}
        for l in db.query(Location).all()
    ]


@router.post("")
def create_location(
    data: LocationCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_role(UserRole.MANAGER)),
):
    if db.query(Location).filter(Location.code == data.code).first():
        raise HTTPException(400, "Location code exists")
    loc = Location(**data.model_dump())
    db.add(loc)
    db.commit()
    return {"id": loc.id}


@router.get("/{location_id}/stock")
def location_stock(
    location_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    items = db.query(InventoryItem).filter_by(location_id=location_id).all()
    return [{
        "product_id": i.product_id,
        "sku": i.product.sku,
        "name": i.product.name,
        "quantity": i.quantity,
        "unit_price": i.product.unit_price,
        "value": i.quantity * i.product.unit_price,
    } for i in items]