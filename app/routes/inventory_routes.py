# app/routes/inventory_routes.py

from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Query,
)

from fastapi.responses import Response

from sqlalchemy.orm import Session
from sqlalchemy import or_

from pydantic import BaseModel

from app.database import get_db

from app.models import (
    Product,
    InventoryItem,
    Location,
    Category,
    Supplier,
    User,
    UserRole,
    Transaction,
    TransactionType,
)

from app.auth import (
    get_current_user,
    require_role,
)

from app.barcode import (
    generate_barcode_image,
    generate_qr_code,
    decode_barcode_from_image,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api",
    tags=["inventory"]
)


# ============================================================
# SCHEMAS
# ============================================================

class ProductCreate(BaseModel):
    sku: str
    name: str

    barcode: Optional[str] = None

    description: str = ""

    category_id: Optional[int] = None

    supplier_id: Optional[int] = None

    unit_price: float = 0.0

    cost_price: float = 0.0

    reorder_level: int = 10

    unit: str = "pcs"

    # Initial stock information
    location_id: int

    quantity: int = 0


class ProductUpdate(BaseModel):
    name: Optional[str] = None

    barcode: Optional[str] = None

    description: Optional[str] = None

    category_id: Optional[int] = None

    supplier_id: Optional[int] = None

    unit_price: Optional[float] = None

    cost_price: Optional[float] = None

    reorder_level: Optional[int] = None

    unit: Optional[str] = None

    is_active: Optional[bool] = None


class StockAdjustment(BaseModel):
    product_id: int

    location_id: int

    quantity: int

    reason: str = ""


# ============================================================
# PRODUCTS - LIST
# ============================================================

@router.get("/products")
def list_products(
    q: Optional[str] = None,
    category_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    query = db.query(Product)

    # Search
    if q:
        query = query.filter(
            or_(
                Product.name.ilike(f"%{q}%"),
                Product.sku.ilike(f"%{q}%"),
                Product.barcode.ilike(f"%{q}%"),
            )
        )

    # Category filter
    if category_id:
        query = query.filter(
            Product.category_id == category_id
        )

    products = (
        query
        .offset(skip)
        .limit(limit)
        .all()
    )

    result = []

    for p in products:

        # Total stock across all locations
        total = sum(
            i.quantity
            for i in p.inventory_items
        )

        # Stock by location
        locations = []

        for i in p.inventory_items:

            locations.append({
                "location_id": i.location_id,

                "location_code": (
                    i.location.code
                    if i.location
                    else None
                ),

                "location_name": (
                    i.location.name
                    if i.location
                    else None
                ),

                "quantity": i.quantity,

                "reserved_quantity": (
                    i.reserved_quantity
                ),

                "available_quantity": (
                    i.available_quantity
                ),
            })

        result.append({

            "id": p.id,

            "sku": p.sku,

            "barcode": p.barcode,

            "name": p.name,

            "description": p.description,

            "category": (
                p.category.name
                if p.category
                else None
            ),

            "supplier": (
                p.supplier.name
                if p.supplier
                else None
            ),

            "unit_price": p.unit_price,

            "cost_price": p.cost_price,

            "reorder_level": p.reorder_level,

            "unit": p.unit,

            "total_stock": total,

            "locations": locations,

            "is_active": p.is_active,

            "needs_reorder": (
                total <= p.reorder_level
            ),
        })

    return result


# ============================================================
# CREATE PRODUCT
# ============================================================

@router.post("/products")
def create_product(
    data: ProductCreate,

    db: Session = Depends(get_db),

    current: User = Depends(
        require_role(UserRole.MANAGER)
    ),
):
    # --------------------------------------------------------
    # Validate SKU
    # --------------------------------------------------------

    existing_sku = (
        db.query(Product)
        .filter(Product.sku == data.sku)
        .first()
    )

    if existing_sku:
        raise HTTPException(
            status_code=400,
            detail="SKU already exists"
        )

    # --------------------------------------------------------
    # Validate barcode
    # --------------------------------------------------------

    if data.barcode:

        existing_barcode = (
            db.query(Product)
            .filter(
                Product.barcode == data.barcode
            )
            .first()
        )

        if existing_barcode:
            raise HTTPException(
                status_code=400,
                detail="Barcode already exists"
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
    # Validate quantity
    # --------------------------------------------------------

    if data.quantity < 0:

        raise HTTPException(
            status_code=400,
            detail="Quantity cannot be negative"
        )

    # --------------------------------------------------------
    # Create product
    # --------------------------------------------------------

    product = Product(
        sku=data.sku,
        name=data.name,
        barcode=data.barcode,
        description=data.description,
        category_id=data.category_id,
        supplier_id=data.supplier_id,
        unit_price=data.unit_price,
        cost_price=data.cost_price,
        reorder_level=data.reorder_level,
        unit=data.unit,
    )

    db.add(product)

    # Generate product ID
    db.flush()

    # --------------------------------------------------------
    # Create inventory record
    # --------------------------------------------------------

    inventory = InventoryItem(
        product_id=product.id,
        location_id=data.location_id,
        quantity=data.quantity,
        reserved_quantity=0,
    )

    db.add(inventory)

    # --------------------------------------------------------
    # Record opening stock as STOCK_IN
    # --------------------------------------------------------

    if data.quantity > 0:

        transaction = Transaction(
            product_id=product.id,

            from_location_id=None,

            to_location_id=data.location_id,

            user_id=current.id,

            transaction_type=TransactionType.STOCK_IN,

            quantity=data.quantity,

            unit_price=data.cost_price,

            total_amount=(
                data.quantity * data.cost_price
            ),

            reference="OPENING-STOCK",

            notes=(
                f"Opening stock for {product.name}"
            ),
        )

        db.add(transaction)

    # --------------------------------------------------------
    # Save everything
    # --------------------------------------------------------

    try:

        db.commit()

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Could not create product: {str(e)}"
        )

    db.refresh(product)

    db.refresh(inventory)

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {

        "message": "Product created successfully",

        "id": product.id,

        "sku": product.sku,

        "name": product.name,

        "barcode": product.barcode,

        "location": {

            "id": location.id,

            "code": location.code,

            "name": location.name,

        },

        "quantity": inventory.quantity,

        "unit": product.unit,

    }


# ============================================================
# LOOKUP PRODUCT BY BARCODE
# ============================================================

@router.get("/products/barcode/{code}")
def lookup_by_barcode(
    code: str,

    db: Session = Depends(get_db),

    current: User = Depends(
        get_current_user
    ),
):
    product = (
        db.query(Product)
        .filter(
            or_(
                Product.barcode == code,
                Product.sku == code,
            )
        )
        .first()
    )

    if not product:

        raise HTTPException(
            status_code=404,
            detail=f"No product found for barcode: {code}"
        )

    stock_by_location = []

    for i in product.inventory_items:

        stock_by_location.append({

            "location_id": i.location_id,

            "location": (
                i.location.name
                if i.location
                else None
            ),

            "location_code": (
                i.location.code
                if i.location
                else None
            ),

            "quantity": i.quantity,

            "reserved_quantity": (
                i.reserved_quantity
            ),

            "available_quantity": (
                i.available_quantity
            ),
        })

    return {

        "id": product.id,

        "sku": product.sku,

        "name": product.name,

        "barcode": product.barcode,

        "unit_price": product.unit_price,

        "stock_by_location": stock_by_location,

        "total_stock": sum(
            item["quantity"]
            for item in stock_by_location
        ),
    }


# ============================================================
# UPDATE PRODUCT
# ============================================================

@router.put("/products/{product_id}")
def update_product(
    product_id: int,

    data: ProductUpdate,

    db: Session = Depends(get_db),

    current: User = Depends(
        require_role(UserRole.MANAGER)
    ),
):
    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .first()
    )

    if not product:

        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    # Check barcode uniqueness
    if data.barcode:

        existing = (
            db.query(Product)
            .filter(
                Product.barcode == data.barcode,
                Product.id != product_id,
            )
            .first()
        )

        if existing:

            raise HTTPException(
                status_code=400,
                detail="Barcode already exists"
            )

    # Update fields
    for key, value in data.model_dump(
        exclude_unset=True
    ).items():

        setattr(
            product,
            key,
            value
        )

    db.commit()

    db.refresh(product)

    return {

        "status": "updated",

        "id": product.id,

        "sku": product.sku,

        "name": product.name,

    }


# ============================================================
# DELETE PRODUCT
# ============================================================

@router.delete("/products/{product_id}")
def delete_product(
    product_id: int,

    db: Session = Depends(get_db),

    current: User = Depends(
        require_role(UserRole.ADMIN)
    ),
):
    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .first()
    )

    if not product:

        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    db.delete(product)

    db.commit()

    return {
        "status": "deleted"
    }


# ============================================================
# BARCODE IMAGE
# ============================================================

@router.get("/products/{product_id}/barcode")
def get_barcode_image(
    product_id: int,

    barcode_type: str = "code128",

    db: Session = Depends(get_db),

    current: User = Depends(
        get_current_user
    ),
):
    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .first()
    )

    if not product:

        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    data = (
        product.barcode
        or product.sku
    )

    img = generate_barcode_image(
        data,
        barcode_type
    )

    return Response(
        content=img,
        media_type="image/png"
    )


# ============================================================
# QR CODE
# ============================================================

@router.get("/products/{product_id}/qrcode")
def get_qr_image(
    product_id: int,

    db: Session = Depends(get_db),

    current: User = Depends(
        get_current_user
    ),
):
    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .first()
    )

    if not product:

        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    img = generate_qr_code(
        product.barcode
        or product.sku
    )

    return Response(
        content=img,
        media_type="image/png"
    )


# ============================================================
# DECODE BARCODE
# ============================================================

@router.post("/products/decode-barcode")
async def decode_barcode(
    file: UploadFile = File(...),

    current: User = Depends(
        get_current_user
    ),
):
    contents = await file.read()

    try:

        code = decode_barcode_from_image(
            contents
        )

    except RuntimeError as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    if not code:

        raise HTTPException(
            status_code=400,
            detail="No barcode detected"
        )

    return {
        "barcode": code
    }


# ============================================================
# STOCK ADJUSTMENT
# ============================================================

@router.post("/stock/adjust")
def adjust_stock(
    data: StockAdjustment,

    db: Session = Depends(get_db),

    current: User = Depends(
        require_role(UserRole.STAFF)
    ),
):
    # --------------------------------------------------------
    # Verify product
    # --------------------------------------------------------

    product = (
        db.query(Product)
        .filter(Product.id == data.product_id)
        .first()
    )

    if not product:

        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    # --------------------------------------------------------
    # Verify location
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
    # Find inventory
    # --------------------------------------------------------

    inv = (
        db.query(InventoryItem)
        .filter_by(
            product_id=data.product_id,
            location_id=data.location_id,
        )
        .first()
    )

    # --------------------------------------------------------
    # Create inventory record if missing
    # --------------------------------------------------------

    if not inv:

        inv = InventoryItem(
            product_id=data.product_id,
            location_id=data.location_id,
            quantity=0,
            reserved_quantity=0,
        )

        db.add(inv)

        db.flush()

    # --------------------------------------------------------
    # Calculate new quantity
    # --------------------------------------------------------

    new_qty = (
        inv.quantity
        + data.quantity
    )

    if new_qty < 0:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient stock. "
                f"Current: {inv.quantity}"
            )
        )

    inv.quantity = new_qty

    # --------------------------------------------------------
    # Determine transaction direction
    # --------------------------------------------------------

    if data.quantity > 0:

        transaction_type = (
            TransactionType.STOCK_IN
        )

        to_location_id = (
            data.location_id
        )

        from_location_id = None

    elif data.quantity < 0:

        transaction_type = (
            TransactionType.STOCK_OUT
        )

        from_location_id = (
            data.location_id
        )

        to_location_id = None

    else:

        transaction_type = (
            TransactionType.ADJUSTMENT
        )

        from_location_id = None

        to_location_id = None

    # --------------------------------------------------------
    # Create transaction
    # --------------------------------------------------------

    tx = Transaction(

        product_id=data.product_id,

        from_location_id=from_location_id,

        to_location_id=to_location_id,

        user_id=current.id,

        transaction_type=transaction_type,

        quantity=abs(data.quantity),

        unit_price=product.cost_price,

        total_amount=(
            abs(data.quantity)
            * product.cost_price
        ),

        reference="STOCK-ADJUSTMENT",

        notes=data.reason,

    )

    db.add(tx)

    db.commit()

    db.refresh(inv)

    return {

        "status": "ok",

        "product_id": data.product_id,

        "product": product.name,

        "location_id": data.location_id,

        "location": location.name,

        "quantity_changed": data.quantity,

        "new_quantity": new_qty,

    }


# ============================================================
# LOW STOCK
# ============================================================

@router.get("/stock/low")
def low_stock(
    db: Session = Depends(get_db),

    current: User = Depends(
        get_current_user
    ),
):
    results = []

    products = (
        db.query(Product)
        .filter(
            Product.is_active == True
        )
        .all()
    )

    for p in products:

        total = sum(
            i.quantity
            for i in p.inventory_items
        )

        if total <= p.reorder_level:

            results.append({

                "id": p.id,

                "sku": p.sku,

                "name": p.name,

                "stock": total,

                "reorder_level": (
                    p.reorder_level
                ),

                "shortage": (
                    p.reorder_level - total
                ),

                "locations": [

                    {
                        "location_id": i.location_id,

                        "location": (
                            i.location.name
                            if i.location
                            else None
                        ),

                        "quantity": i.quantity,

                    }

                    for i in p.inventory_items
                ],
            })

    return results