# app/bulk_ops.py
import io
import pandas as pd
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from app.models import Product, Category, Supplier, InventoryItem, Location


REQUIRED_PRODUCT_COLUMNS = ["sku", "name", "unit_price"]
OPTIONAL_PRODUCT_COLUMNS = [
    "barcode", "description", "category", "supplier",
    "cost_price", "reorder_level", "unit", "initial_quantity"
]


def parse_products_csv(file_bytes: bytes) -> Tuple[List[Dict], List[str]]:
    """Parse CSV, return rows and errors"""
    df = pd.read_csv(io.BytesIO(file_bytes))
    df.columns = [c.strip().lower() for c in df.columns]
    
    errors = []
    missing = [c for c in REQUIRED_PRODUCT_COLUMNS if c not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {missing}")
        return [], errors
    
    return df.to_dict(orient="records"), errors


def bulk_import_products(
    db: Session, rows: List[Dict], location_id: int = None
) -> Dict[str, any]:
    """Import products in bulk. Returns stats."""
    created = 0
    updated = 0
    failed = 0
    errors = []
    
    # Default location
    if not location_id:
        default_loc = db.query(Location).first()
        location_id = default_loc.id if default_loc else None
    
    for idx, row in enumerate(rows, start=2):
        try:
            sku = str(row["sku"]).strip()
            existing = db.query(Product).filter(Product.sku == sku).first()
            
            # Resolve category
            cat_id = None
            if row.get("category"):
                cat = db.query(Category).filter(Category.name == str(row["category"]).strip()).first()
                if not cat:
                    cat = Category(name=str(row["category"]).strip())
                    db.add(cat)
                    db.flush()
                cat_id = cat.id
            
            # Resolve supplier
            sup_id = None
            if row.get("supplier"):
                sup = db.query(Supplier).filter(Supplier.name == str(row["supplier"]).strip()).first()
                if not sup:
                    sup = Supplier(name=str(row["supplier"]).strip())
                    db.add(sup)
                    db.flush()
                sup_id = sup.id
            
            data = {
                "sku": sku,
                "name": str(row["name"]).strip(),
                "barcode": str(row.get("barcode", "")).strip() or None,
                "description": str(row.get("description", "")),
                "category_id": cat_id,
                "supplier_id": sup_id,
                "unit_price": float(row.get("unit_price", 0)),
                "cost_price": float(row.get("cost_price", 0)),
                "reorder_level": int(row.get("reorder_level", 10)),
                "unit": str(row.get("unit", "pcs")),
            }
            
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                product = Product(**data)
                db.add(product)
                db.flush()
                created += 1
                existing = product
                
                # Add initial stock
                qty = int(row.get("initial_quantity", 0) or 0)
                if qty > 0 and location_id:
                    inv = InventoryItem(
                        product_id=existing.id,
                        location_id=location_id,
                        quantity=qty
                    )
                    db.add(inv)
        except Exception as e:
            failed += 1
            errors.append(f"Row {idx}: {str(e)}")
    
    db.commit()
    return {
        "created": created,
        "updated": updated,
        "failed": failed,
        "errors": errors[:20],  # Limit errors shown
    }


def export_products_csv(db: Session) -> str:
    """Export all products + stock as CSV string"""
    products = db.query(Product).all()
    rows = []
    for p in products:
        total_stock = sum(i.quantity for i in p.inventory_items)
        rows.append({
            "sku": p.sku,
            "barcode": p.barcode or "",
            "name": p.name,
            "category": p.category.name if p.category else "",
            "supplier": p.supplier.name if p.supplier else "",
            "unit_price": p.unit_price,
            "cost_price": p.cost_price,
            "reorder_level": p.reorder_level,
            "unit": p.unit,
            "total_stock": total_stock,
            "is_active": p.is_active,
        })
    
    if not rows:
        return "sku,name,unit_price\n"
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


import csv