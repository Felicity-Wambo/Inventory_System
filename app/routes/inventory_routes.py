# app/routes/inventory_routes.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models import Product, InventoryItem, Location, Category, Supplier, User, UserRole
from app.auth import get_current_user, require_role
from app.barcode import (
    generate_barcode_image, generate_qr_code, decode_barcode_from_image
)

router = APIRouter(prefix="/api", tags=["inventory"])


# ---------- Schemas ----------
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


# ---------- Products ----------
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
    if q:
        query = query.filter(or_(
            Product.name.ilike(f"%{q}%"),
            Product.sku.ilike(f"%{q}%"),
            Product.barcode.ilike(f"%{q}%"),
        ))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    
    products = query.offset(skip).limit(limit).all()
    result = []
    for p in products:
        total = sum(i.quantity for i in p.inventory_items)
        result.append({
            "id": p.id, "sku": p.sku, "barcode": p.barcode, "name": p.name,
            "category": p.category.name if p.category else None,
            "supplier": p.supplier.name if p.supplier else None,
            "unit_price": p.unit_price, "cost_price": p.cost_price,
            "reorder_level": p.reorder_level, "unit": p.unit,
            "total_stock": total, "is_active": p.is_active,
            "needs_reorder": total <= p.reorder_level,
        })
    return result


@router.get("/products/barcode/{code}")
def lookup_by_barcode(
    code: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Barcode scanning lookup endpoint"""
    product = db.query(Product).filter(
        or_(Product.barcode == code, Product.sku == code)
    ).first()
    if not product:
        raise HTTPException(404, f"No product found for barcode: {code}")
    
    stock_by_location = [
        {
            "location_id": i.location_id,
            "location": i.location.name,
            "quantity": i.quantity,
        }
        for i in product.inventory_items
    ]
    
    return {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "barcode": product.barcode,
        "unit_price": product.unit_price,
        "stock_by_location": stock_by_location,
        "total_stock": sum(i["quantity"] for i in stock_by_location),
    }


@router.post("/products")
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_role(UserRole.MANAGER)),
):
    if db.query(Product).filter(Product.sku == data.sku).first():
        raise HTTPException(400, "SKU already exists")
    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return {"id": product.id, "sku": product.sku}


@router.put("/products/{product_id}")
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_role(UserRole.MANAGER)),
):
    product = db.query(Product).get(product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(product, k, v)
    db.commit()
    return {"status": "updated"}


@router.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_role(UserRole.ADMIN)),
):
    product = db.query(Product).get(product_id)
    if not product:
        raise HTTPException(404, "Not found")
    db.delete(product)
    db.commit()
    return {"status": "deleted"}


# ---------- Barcode generation ----------
@router.get("/products/{product_id}/barcode")
def get_barcode_image(
    product_id: int,
    barcode_type: str = "code128",
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    product = db.query(Product).get(product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    data = product.barcode or product.sku
    img = generate_barcode_image(data, barcode_type)
    return Response(content=img, media_type="image/png")


@router.get("/products/{product_id}/qrcode")
def get_qr_image(
    product_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    product = db.query(Product).get(product_id)
    if not product:
        raise HTTPException(404, "Not found")
    img = generate_qr_code(product.barcode or product.sku)
    return Response(content=img, media_type="image/png")


@router.post("/products/decode-barcode")
async def decode_barcode(
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
):
    """Upload a barcode image and get the decoded value"""
    contents = await file.read()
    try:
        code = decode_barcode_from_image(contents)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    if not code:
        raise HTTPException(400, "No barcode detected")
    return {"barcode": code}


# ---------- Stock management ----------
@router.post("/stock/adjust")
def adjust_stock(
    data: StockAdjustment,
    db: Session = Depends(get_db),
    current: User = Depends(require_role(UserRole.STAFF)),
):
    from app.models import Transaction, TransactionType
    
    inv = db.query(InventoryItem).filter_by(
        product_id=data.product_id, location_id=data.location_id
    ).first()
    
    if not inv:
        inv = InventoryItem(
            product_id=data.product_id,
            location_id=data.location_id,
            quantity=0,
        )
        db.add(inv)
        db.flush()
    
    new_qty = inv.quantity + data.quantity
    if new_qty < 0:
        raise HTTPException(400, f"Insufficient stock. Current: {inv.quantity}")
    
    inv.quantity = new_qty
    
    # Log transaction
    tx = Transaction(
        product_id=data.product_id,
        to_location_id=data.location_id if data.quantity > 0 else None,
        from_location_id=data.location_id if data.quantity < 0 else None,
        user_id=current.id,
        transaction_type=TransactionType.ADJUSTMENT,
        quantity=abs(data.quantity),
        notes=data.reason,
    )
    db.add(tx)
    db.commit()
    
    return {"status": "ok", "new_quantity": new_qty}


@router.get("/stock/low")
def low_stock(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    results = []
    for p in db.query(Product).filter(Product.is_active == True).all():
        total = sum(i.quantity for i in p.inventory_items)
        if total <= p.reorder_level:
            results.append({
                "id": p.id, "sku": p.sku, "name": p.name,
                "stock": total, "reorder_level": p.reorder_level,
                "shortage": p.reorder_level - total,
            })
    return results