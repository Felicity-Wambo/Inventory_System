# app/routes/purchase_routes.py

import datetime
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

from app.database import get_db

from app.models import (
    InventoryItem,
    Purchase,
    PurchaseItem,
    PurchaseStatus,
    Product,
    Supplier,
    Location,
    Transaction,
    TransactionType,
    User,
    UserRole,
)

from app.auth import (
    get_current_user,
    require_role,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/purchases",
    tags=["purchases"]
)


# ============================================================
# SCHEMAS
# ============================================================

class PurchaseItemCreate(BaseModel):
    product_id: int

    quantity: int = Field(
        gt=0,
        description="Quantity purchased"
    )

    unit_cost: float = Field(
        ge=0,
        description="Cost per unit"
    )


class PurchaseCreate(BaseModel):
    supplier_id: int

    location_id: int

    invoice_number: Optional[str] = None

    tax: float = Field(
        default=0.0,
        ge=0
    )

    notes: Optional[str] = None

    items: List[PurchaseItemCreate]


# ============================================================
# GENERATE PURCHASE NUMBER
# ============================================================

def generate_purchase_number(db: Session) -> str:
    """
    Generates purchase numbers such as:

    PO-000001
    PO-000002
    PO-000003
    """

    last_purchase = (
        db.query(Purchase)
        .order_by(Purchase.id.desc())
        .first()
    )

    if not last_purchase:
        next_number = 1
    else:
        next_number = last_purchase.id + 1

    return f"PO-{next_number:06d}"


# ============================================================
# CREATE PURCHASE
# ============================================================

@router.post("")
def create_purchase(
    data: PurchaseCreate,

    db: Session = Depends(get_db),

    current: User = Depends(
        require_role("manager")
    ),
):
    """
    Creates a purchase in DRAFT status.

    This does NOT change inventory yet.

    Inventory will be updated when the purchase
    is received.
    """

    # --------------------------------------------------------
    # Validate supplier
    # --------------------------------------------------------

    supplier = (
        db.query(Supplier)
        .filter(
            Supplier.id == data.supplier_id
        )
        .first()
    )

    if not supplier:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found"
        )

    # --------------------------------------------------------
    # Validate location
    # --------------------------------------------------------

    location = (
        db.query(Location)
        .filter(
            Location.id == data.location_id,
            Location.is_active == True
        )
        .first()
    )

    if not location:
        raise HTTPException(
            status_code=404,
            detail="Location not found or inactive"
        )

    # --------------------------------------------------------
    # Validate items
    # --------------------------------------------------------

    if not data.items:
        raise HTTPException(
            status_code=400,
            detail="Purchase must contain at least one item"
        )

    # --------------------------------------------------------
    # Generate purchase number
    # --------------------------------------------------------

    purchase_number = generate_purchase_number(db)

    # --------------------------------------------------------
    # Calculate subtotal
    # --------------------------------------------------------

    subtotal = 0.0

    validated_items = []

    for item in data.items:

        product = (
            db.query(Product)
            .filter(
                Product.id == item.product_id,
                Product.is_active == True
            )
            .first()
        )

        if not product:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Product {item.product_id} "
                    f"not found or inactive"
                )
            )

        total_cost = (
            item.quantity
            * item.unit_cost
        )

        subtotal += total_cost

        validated_items.append({
            "product": product,
            "quantity": item.quantity,
            "unit_cost": item.unit_cost,
            "total_cost": total_cost,
        })

    # --------------------------------------------------------
    # Calculate total
    # --------------------------------------------------------

    total_amount = (
        subtotal
        + data.tax
    )

    # --------------------------------------------------------
    # Create purchase
    # --------------------------------------------------------

    purchase = Purchase(

        supplier_id=data.supplier_id,

        location_id=data.location_id,

        user_id=current.id,

        purchase_number=purchase_number,

        invoice_number=data.invoice_number,

        status=PurchaseStatus.DRAFT,

        subtotal=subtotal,

        tax=data.tax,

        total_amount=total_amount,

        notes=data.notes,
    )

    db.add(purchase)

    db.flush()

    # --------------------------------------------------------
    # Create purchase items
    # --------------------------------------------------------

    for item in validated_items:

        purchase_item = PurchaseItem(

            purchase_id=purchase.id,

            product_id=item["product"].id,

            quantity=item["quantity"],

            unit_cost=item["unit_cost"],

            total_cost=item["total_cost"],
        )

        db.add(purchase_item)

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    try:

        db.commit()

        db.refresh(purchase)

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Could not create purchase: {str(e)}"
        )

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {

        "message": "Purchase created successfully",

        "id": purchase.id,

        "purchase_number": (
            purchase.purchase_number
        ),

        "supplier": supplier.name,

        "location": location.name,

        "status": purchase.status.value,

        "subtotal": purchase.subtotal,

        "tax": purchase.tax,

        "total_amount": (
            purchase.total_amount
        ),

        "items": [

            {
                "product_id": item["product"].id,

                "product": item["product"].name,

                "quantity": item["quantity"],

                "unit_cost": item["unit_cost"],

                "total_cost": item["total_cost"],
            }

            for item in validated_items
        ],
    }


# ============================================================
# LIST PURCHASES
# ============================================================

@router.get("")
def list_purchases(
    db: Session = Depends(get_db),

    current: User = Depends(
        get_current_user
    ),
):
    """
    Returns all purchases.
    """

    purchases = (
        db.query(Purchase)
        .order_by(
            Purchase.id.desc()
        )
        .all()
    )

    results = []

    for purchase in purchases:

        results.append({

            "id": purchase.id,

            "purchase_number": (
                purchase.purchase_number
            ),

            "invoice_number": (
                purchase.invoice_number
            ),

            "supplier": (
                purchase.supplier.name
                if purchase.supplier
                else None
            ),

            "location": (
                purchase.location.name
                if purchase.location
                else None
            ),

            "status": (
                purchase.status.value
            ),

            "subtotal": (
                purchase.subtotal
            ),

            "tax": (
                purchase.tax
            ),

            "total_amount": (
                purchase.total_amount
            ),

            "notes": purchase.notes,

            "created_at": (
                purchase.created_at
            ),

            "received_at": (
                purchase.received_at
            ),

            "items": [

                {
                    "id": item.id,

                    "product_id": item.product_id,

                    "product": (
                        item.product.name
                        if item.product
                        else None
                    ),

                    "quantity": item.quantity,

                    "unit_cost": item.unit_cost,

                    "total_cost": (
                        item.total_cost
                    ),
                }

                for item in purchase.items
            ],
        })

    return results


# ============================================================
# GET SINGLE PURCHASE
# ============================================================

@router.get("/{purchase_id}")
def get_purchase(
    purchase_id: int,

    db: Session = Depends(get_db),

    current: User = Depends(
        get_current_user
    ),
):
    """
    Returns one purchase and all its items.
    """

    purchase = (
        db.query(Purchase)
        .filter(
            Purchase.id == purchase_id
        )
        .first()
    )

    if not purchase:

        raise HTTPException(
            status_code=404,
            detail="Purchase not found"
        )

    return {

        "id": purchase.id,

        "purchase_number": (
            purchase.purchase_number
        ),

        "invoice_number": (
            purchase.invoice_number
        ),

        "supplier": (
            purchase.supplier.name
            if purchase.supplier
            else None
        ),

        "location": (
            purchase.location.name
            if purchase.location
            else None
        ),

        "status": (
            purchase.status.value
        ),

        "subtotal": purchase.subtotal,

        "tax": purchase.tax,

        "total_amount": (
            purchase.total_amount
        ),

        "notes": purchase.notes,

        "created_at": (
            purchase.created_at
        ),

        "received_at": (
            purchase.received_at
        ),

        "items": [

            {
                "id": item.id,

                "product_id": item.product_id,

                "product": (
                    item.product.name
                    if item.product
                    else None
                ),

                "quantity": item.quantity,

                "unit_cost": item.unit_cost,

                "total_cost": (
                    item.total_cost
                ),
            }

            for item in purchase.items
        ],
    }
@router.post("/{purchase_id}/receive")
def receive_purchase(
    purchase_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_role(UserRole.MANAGER)),
):
    purchase = (
        db.query(Purchase)
        .filter(Purchase.id == purchase_id)
        .first()
    )

    if not purchase:
        raise HTTPException(
            status_code=404,
            detail="Purchase not found"
        )

    if purchase.status == PurchaseStatus.RECEIVED:
        raise HTTPException(
            status_code=400,
            detail="Purchase has already been received"
        )

    if purchase.status == PurchaseStatus.CANCELLED:
        raise HTTPException(
            status_code=400,
            detail="Cancelled purchase cannot be received"
        )

    if not purchase.items:
        raise HTTPException(
            status_code=400,
            detail="Purchase has no items"
        )

    try:
        for item in purchase.items:

            inventory = (
                db.query(InventoryItem)
                .filter(
                    InventoryItem.product_id == item.product_id,
                    InventoryItem.location_id == purchase.location_id
                )
                .first()
            )

            if not inventory:
                inventory = InventoryItem(
                    product_id=item.product_id,
                    location_id=purchase.location_id,
                    quantity=0
                )

                db.add(inventory)

            # Increase inventory
            inventory.quantity += item.quantity

            # Record STOCK IN transaction
            transaction = Transaction(
                product_id=item.product_id,
                from_location_id=None,
                to_location_id=purchase.location_id,
                user_id=current.id,
                transaction_type=TransactionType.STOCK_IN,
                quantity=item.quantity,
                unit_price=item.unit_cost,
                total_amount=item.total_cost,
                reference=purchase.purchase_number,
                notes=f"Purchase received: {purchase.purchase_number}"
            )

            db.add(transaction)

        # Update purchase
        purchase.status = PurchaseStatus.RECEIVED
        purchase.received_at = datetime.utcnow()

        db.commit()
        db.refresh(purchase)

        return {
            "message": "Purchase received successfully",
            "purchase_id": purchase.id,
            "purchase_number": purchase.purchase_number,
            "status": purchase.status.value,
            "received_at": purchase.received_at.isoformat()
        }

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to receive purchase: {str(e)}"
        )