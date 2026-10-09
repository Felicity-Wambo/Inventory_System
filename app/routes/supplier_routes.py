# app/routes/supplier_routes.py

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Supplier, User, UserRole
from app.auth import get_current_user, require_role


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/suppliers",
    tags=["suppliers"]
)


# ============================================================
# SCHEMAS
# ============================================================

class SupplierCreate(BaseModel):
    name: str
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


# ============================================================
# LIST SUPPLIERS
# ============================================================

@router.get("")
def list_suppliers(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    suppliers = (
        db.query(Supplier)
        .order_by(Supplier.name.asc())
        .all()
    )

    return [
        {
            "id": supplier.id,
            "name": supplier.name,
            "contact_email": supplier.contact_email,
            "phone": supplier.phone,
            "address": supplier.address,
        }
        for supplier in suppliers
    ]


# ============================================================
# GET SINGLE SUPPLIER
# ============================================================

@router.get("/{supplier_id}")
def get_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    supplier = (
        db.query(Supplier)
        .filter(Supplier.id == supplier_id)
        .first()
    )

    if not supplier:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found"
        )

    return {
        "id": supplier.id,
        "name": supplier.name,
        "contact_email": supplier.contact_email,
        "phone": supplier.phone,
        "address": supplier.address,
    }


# ============================================================
# CREATE SUPPLIER
# ============================================================

@router.post("")
def create_supplier(
    data: SupplierCreate,
    db: Session = Depends(get_db),
    current: User = Depends(
        require_role(UserRole.MANAGER)
    ),
):
    name = data.name.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Supplier name is required"
        )

    existing = (
        db.query(Supplier)
        .filter(Supplier.name.ilike(name))
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Supplier already exists"
        )

    supplier = Supplier(
        name=name,
        contact_email=data.contact_email,
        phone=data.phone,
        address=data.address,
    )

    db.add(supplier)

    try:
        db.commit()
        db.refresh(supplier)

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Could not create supplier: {str(e)}"
        )

    return {
        "message": "Supplier created successfully",
        "id": supplier.id,
        "name": supplier.name,
        "contact_email": supplier.contact_email,
        "phone": supplier.phone,
        "address": supplier.address,
    }


# ============================================================
# UPDATE SUPPLIER
# ============================================================

@router.put("/{supplier_id}")
def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(
        require_role(UserRole.MANAGER)
    ),
):
    supplier = (
        db.query(Supplier)
        .filter(Supplier.id == supplier_id)
        .first()
    )

    if not supplier:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found"
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

    if "name" in update_data:

        name = update_data["name"].strip()

        if not name:
            raise HTTPException(
                status_code=400,
                detail="Supplier name cannot be empty"
            )

        existing = (
            db.query(Supplier)
            .filter(
                Supplier.name.ilike(name),
                Supplier.id != supplier_id,
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail="Another supplier with this name already exists"
            )

        update_data["name"] = name

    for key, value in update_data.items():
        setattr(supplier, key, value)

    try:
        db.commit()
        db.refresh(supplier)

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Could not update supplier: {str(e)}"
        )

    return {
        "message": "Supplier updated successfully",
        "id": supplier.id,
        "name": supplier.name,
        "contact_email": supplier.contact_email,
        "phone": supplier.phone,
        "address": supplier.address,
    }


# ============================================================
# DELETE SUPPLIER
# ============================================================

@router.delete("/{supplier_id}")
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(
        require_role(UserRole.MANAGER)
    ),
):
    supplier = (
        db.query(Supplier)
        .filter(Supplier.id == supplier_id)
        .first()
    )

    if not supplier:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found"
        )

    # Do not physically delete suppliers that may
    # already be connected to products or purchases.
    # Instead, remove the supplier relationship from
    # products and purchases before deleting if needed.

    try:
        db.delete(supplier)
        db.commit()

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=(
                "Supplier cannot be deleted because it may "
                "be linked to existing records. "
                f"Details: {str(e)}"
            )
        )

    return {
        "message": "Supplier deleted successfully",
        "id": supplier_id,
    }