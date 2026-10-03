# app/routes/report_routes.py
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
from app.database import get_db
from app.models import Product, Transaction, InventoryItem, Location, User
from app.auth import get_current_user
from app.reports import generate_csv, generate_pdf_report
from app.bulk_ops import (
    parse_products_csv, bulk_import_products, export_products_csv
)

router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/reports/inventory/pdf")
def inventory_pdf(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    products = db.query(Product).all()
    data = []
    total_value = 0
    for p in products:
        stock = sum(i.quantity for i in p.inventory_items)
        value = stock * p.unit_price
        total_value += value
        data.append({
            "sku": p.sku, "name": p.name,
            "category": p.category.name if p.category else "",
            "stock": stock, "price": f"${p.unit_price:.2f}",
            "value": f"${value:.2f}",
            "status": "REORDER" if stock <= p.reorder_level else "OK",
        })
    
    pdf = generate_pdf_report(
        "Inventory Report",
        data,
        headers=["sku", "name", "category", "stock", "price", "value", "status"],
        column_widths=[1.2*inch for _ in range(7)] if False else None,
        summary={
            "Total Products": len(products),
            "Total Value": f"${total_value:,.2f}",
        }
    )
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=inventory.pdf"})


@router.get("/reports/inventory/csv")
def inventory_csv(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    csv_data = export_products_csv(db)
    return Response(
        content=csv_data, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory.csv"}
    )


@router.get("/reports/transactions/csv")
def transactions_csv(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    txs = db.query(Transaction).all()
    data = [{
        "id": t.id,
        "date": t.created_at.isoformat(),
        "product": t.product.name if t.product else "",
        "sku": t.product.sku if t.product else "",
        "type": t.transaction_type.value,
        "quantity": t.quantity,
        "from": t.from_location.name if t.from_location else "",
        "to": t.to_location.name if t.to_location else "",
        "user": t.user.username,
        "amount": t.total_amount,
    } for t in txs]
    csv_data = generate_csv(data)
    return Response(content=csv_data, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=transactions.csv"})


@router.get("/reports/low-stock/pdf")
def low_stock_pdf(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    data = []
    for p in db.query(Product).filter(Product.is_active == True).all():
        stock = sum(i.quantity for i in p.inventory_items)
        if stock <= p.reorder_level:
            data.append({
                "sku": p.sku, "name": p.name,
                "stock": stock,
                "reorder_level": p.reorder_level,
                "shortage": p.reorder_level - stock,
            })
    pdf = generate_pdf_report(
        "Low Stock Report", data,
        headers=["sku", "name", "stock", "reorder_level", "shortage"],
        summary={"Items Needing Reorder": len(data)}
    )
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=low_stock.pdf"})


@router.post("/bulk/import/products")
async def bulk_import(
    file: UploadFile = File(...),
    location_id: int = None,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    contents = await file.read()
    rows, errors = parse_products_csv(contents)
    if errors:
        return {"errors": errors}
    stats = bulk_import_products(db, rows, location_id)
    return stats


@router.get("/bulk/export/products")
def bulk_export(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    csv_data = export_products_csv(db)
    return Response(content=csv_data, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=products.csv"})