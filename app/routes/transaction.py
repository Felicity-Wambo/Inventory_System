# app/routes/transaction_routes.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.database import get_db
from app.models import (
    Transaction, TransactionType, InventoryItem,
    Product, Location, User, UserRole
)
from app.auth import get_current_user, require_role

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


class TransactionCreate(BaseModel):
    product_id: int
    transaction_type: TransactionType
    quantity: int
    from_location_id: Optional[int] = None
    to_location_id: Optional[int] = None
    unit_price: float = 0.0
    reference: str = ""
    notes: str = ""


@router.post("")
def create_transaction(
    data: TransactionCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_role(UserRole.STAFF)),
):
    product = db.query(Product).get(data.product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    
    # Handle stock movement
    if data.transaction_type in (TransactionType.STOCK_IN, TransactionType.RETURN):
        if not data.to_location_id:
            raise HTTPException(400, "to_location_id required for stock in")
        inv = db.query(InventoryItem).filter_by(
            product_id=data.product_id, location_id=data.to_location_id
        ).first()
        if not inv:
            inv = InventoryItem(
                product_id=data.product_id,
                location_id=data.to_location_id, quantity=0
            )
            db.add(inv)
        inv.quantity += data.quantity
    
    elif data.transaction_type in (TransactionType.STOCK_OUT, TransactionType.SALE):
        if not data.from_location_id:
            raise HTTPException(400, "from_location_id required for stock out")
        inv = db.query(InventoryItem).filter_by(
            product_id=data.product_id, location_id=data.from_location_id
        ).first()
        if not inv or inv.quantity < data.quantity:
            raise HTTPException(400, "Insufficient stock")
        inv.quantity -= data.quantity
    
    elif data.transaction_type == TransactionType.TRANSFER:
        if not data.from_location_id or not data.to_location_id:
            raise HTTPException(400, "Both locations required for transfer")
        src = db.query(InventoryItem).filter_by(
            product_id=data.product_id, location_id=data.from_location_id
        ).first()
        if not src or src.quantity < data.quantity:
            raise HTTPException(400, "Insufficient stock at source")
        dst = db.query(InventoryItem).filter_by(
            product_id=data.product_id, location_id=data.to_location_id
        ).first()
        if not dst:
            dst = InventoryItem(
                product_id=data.product_id,
                location_id=data.to_location_id, quantity=0
            )
            db.add(dst)
        src.quantity -= data.quantity
        dst.quantity += data.quantity
    
    tx = Transaction(
        **data.model_dump(),
        user_id=current.id,
        total_amount=data.quantity * data.unit_price,
    )
    db.add(tx)
    db.commit()
    return {"id": tx.id, "status": "recorded"}


@router.get("")
def list_transactions(
    product_id: Optional[int] = None,
    user_id: Optional[int] = None,
    location_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    q = db.query(Transaction)
    if product_id:
        q = q.filter(Transaction.product_id == product_id)
    if user_id:
        q = q.filter(Transaction.user_id == user_id)
    if location_id:
        q = q.filter(
            (Transaction.from_location_id == location_id) |
            (Transaction.to_location_id == location_id)
        )
    if start_date:
        q = q.filter(Transaction.created_at >= start_date)
    if end_date:
        q = q.filter(Transaction.created_at <= end_date)
    
    txs = q.order_by(Transaction.created_at.desc()).offset(skip).limit(limit).all()
    return [{
        "id": t.id,
        "product": t.product.name if t.product else "N/A",
        "type": t.transaction_type.value,
        "quantity": t.quantity,
        "from_location": t.from_location.name if t.from_location else None,
        "to_location": t.to_location.name if t.to_location else None,
        "user": t.user.username,
        "unit_price": t.unit_price,
        "total_amount": t.total_amount,
        "reference": t.reference,
        "notes": t.notes,
        "created_at": t.created_at.isoformat(),
    } for t in txs]