
from datetime import datetime
from uuid import uuid4
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Sale,
    SaleItem,
    Product,
    Location,
    InventoryItem,
    Transaction,
    TransactionType,
    User,
    UserRole,
)
from app.auth import require_role


router = APIRouter(prefix="/api/pos", tags=["Point of Sale"])


# --------------------------------------------------
# REQUEST SCHEMAS
# --------------------------------------------------

class POSItem(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class POSCheckout(BaseModel):
    location_id: int
    items: List[POSItem] = Field(min_length=1)
    discount: float = Field(default=0.0, ge=0)
    tax: float = Field(default=0.0, ge=0)
    payment_method: str = "cash"
    amount_paid: float = Field(ge=0)
    notes: Optional[str] = None


# --------------------------------------------------
# CHECKOUT
# --------------------------------------------------

@router.post("/checkout")
def checkout(
    data: POSCheckout,
    db: Session = Depends(get_db),
    current: User = Depends(require_role(UserRole.STAFF)),
):
    try:
        # Validate the location
        location = db.query(Location).filter(
            Location.id == data.location_id,
            Location.is_active == True,
        ).first()

        if not location:
            raise HTTPException(
                status_code=404,
                detail="Location not found or inactive",
            )

        # Validate payment method
        allowed_methods = {"cash", "mpesa", "card", "bank"}
        payment_method = data.payment_method.strip().lower()

        if payment_method not in allowed_methods:
            raise HTTPException(
                status_code=400,
                detail="Payment method must be cash, mpesa, card, or bank",
            )

        # Combine duplicate product entries in the cart
        quantities = {}
        for item in data.items:
            quantities[item.product_id] = (
                quantities.get(item.product_id, 0) + item.quantity
            )

        # Validate every item and stock before changing inventory
        prepared_items = []
        subtotal = 0.0

        for product_id, quantity in quantities.items():
            product = db.query(Product).filter(
                Product.id == product_id,
                Product.is_active == True,
            ).first()

            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"Product {product_id} not found or inactive",
                )

            inventory = db.query(InventoryItem).filter_by(
                product_id=product_id,
                location_id=data.location_id,
            ).with_for_update().first()

            if not inventory:
                raise HTTPException(
                    status_code=400,
                    detail=f"No inventory found for {product.name} at {location.name}",
                )

            available = (
                inventory.quantity - (inventory.reserved_quantity or 0)
            )

            if available < quantity:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Insufficient stock for {product.name}. "
                        f"Available: {available}, requested: {quantity}"
                    ),
                )

            unit_price = float(product.unit_price or 0)
            line_total = round(unit_price * quantity, 2)

            prepared_items.append({
                "product": product,
                "inventory": inventory,
                "quantity": quantity,
                "unit_price": unit_price,
                "unit_cost": float(product.cost_price or 0),
                "line_total": line_total,
            })

            subtotal += line_total

        subtotal = round(subtotal, 2)

        if data.discount > subtotal:
            raise HTTPException(
                status_code=400,
                detail="Discount cannot exceed the subtotal",
            )

        total = round(subtotal - data.discount + data.tax, 2)

        if data.amount_paid < total:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient payment. Total: {total:.2f}, "
                    f"paid: {data.amount_paid:.2f}"
                ),
            )

        change = round(data.amount_paid - total, 2)

        # Generate a unique receipt number
        sale_number = f"SALE-{datetime.utcnow():%Y%m%d%H%M%S}-{uuid4().hex[:6].upper()}"

        # Save the sale header
        sale = Sale(
            sale_number=sale_number,
            location_id=data.location_id,
            user_id=current.id,
            subtotal=subtotal,
            discount=round(data.discount, 2),
            tax=round(data.tax, 2),
            total_amount=total,
            payment_method=payment_method,
            amount_paid=round(data.amount_paid, 2),
            change_amount=change,
            status="completed",
        )

        db.add(sale)
        db.flush()

        # Save items, deduct stock, and create audit transactions
        for item in prepared_items:
            inventory = item["inventory"]
            product = item["product"]
            quantity = item["quantity"]

            inventory.quantity -= quantity

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=item["unit_price"],
                unit_cost=item["unit_cost"],
                total_price=item["line_total"],
            )
            db.add(sale_item)

            transaction = Transaction(
                product_id=product.id,
                from_location_id=data.location_id,
                to_location_id=None,
                user_id=current.id,
                transaction_type=TransactionType.SALE,
                quantity=quantity,
                unit_price=item["unit_price"],
                total_amount=item["line_total"],
                reference=sale_number,
                notes=data.notes or "POS sale",
            )
            db.add(transaction)

        db.commit()

        return {
            "success": True,
            "message": "Sale completed successfully",
            "sale_id": sale.id,
            "sale_number": sale_number,
            "location": location.name,
            "subtotal": subtotal,
            "discount": round(data.discount, 2),
            "tax": round(data.tax, 2),
            "total_amount": total,
            "payment_method": payment_method,
            "amount_paid": round(data.amount_paid, 2),
            "change_amount": change,
            "items": [
                {
                    "product_id": item["product"].id,
                    "product_name": item["product"].name,
                    "quantity": item["quantity"],
                    "unit_price": item["unit_price"],
                    "total_price": item["line_total"],
                }
                for item in prepared_items
            ],
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Checkout failed. No sale changes were saved.",
        )


# --------------------------------------------------
# LIST RECENT SALES
# --------------------------------------------------

@router.get("/sales")
def list_sales(
    limit: int = 50,
    db: Session = Depends(get_db),
    current: User = Depends(require_role(UserRole.STAFF)),
):
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100",
        )

    sales = (
        db.query(Sale)
        .order_by(Sale.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": sale.id,
            "sale_number": sale.sale_number,
            "location": (
                db.query(Location).filter(
                    Location.id == sale.location_id
                ).first().name
            ),
            "cashier_id": sale.user_id,
            "subtotal": sale.subtotal,
            "discount": sale.discount,
            "tax": sale.tax,
            "total_amount": sale.total_amount,
            "payment_method": sale.payment_method,
            "amount_paid": sale.amount_paid,
            "change_amount": sale.change_amount,
            "status": sale.status,
            "created_at": sale.created_at.isoformat(),
            "items": [
                {
                    "product_id": item.product_id,
                    "product_name": (
                        item.product.name if item.product else "Unknown"
                    ),
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price,
                }
                for item in sale.items
            ],
        }
        for sale in sales
    ]