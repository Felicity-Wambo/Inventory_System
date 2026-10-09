# app/models.py

from datetime import datetime
import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    DateTime,
    Boolean,
    Text,
    Enum,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ============================================================
# ENUMS
# ============================================================

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    STAFF = "staff"
    VIEWER = "viewer"


class TransactionType(str, enum.Enum):
    STOCK_IN = "stock_in"
    STOCK_OUT = "stock_out"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"
    SALE = "sale"
    RETURN = "return"


class PurchaseStatus(str, enum.Enum):
    DRAFT = "draft"
    RECEIVED = "received"
    CANCELLED = "cancelled"


# ============================================================
# USER
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    username = Column(
        String(50),
        unique=True,
        index=True,
        nullable=False
    )

    email = Column(
        String(120),
        unique=True,
        index=True,
        nullable=False
    )

    hashed_password = Column(
        String(255),
        nullable=False
    )

    full_name = Column(
        String(100)
    )

    role = Column(
        Enum(UserRole),
        default=UserRole.STAFF,
        nullable=False
    )

    is_active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    last_login = Column(
        DateTime,
        nullable=True
    )

    # Purchases created by this user
    purchases = relationship(
        "Purchase",
        back_populates="user"
    )


# ============================================================
# LOCATION
# ============================================================

class Location(Base):
    __tablename__ = "locations"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    code = Column(
        String(20),
        unique=True,
        index=True,
        nullable=False
    )

    name = Column(
        String(100),
        nullable=False
    )

    address = Column(
        Text
    )

    is_active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    inventory_items = relationship(
        "InventoryItem",
        back_populates="location"
    )

    # Purchases received at this location
    purchases = relationship(
        "Purchase",
        back_populates="location"
    )


# ============================================================
# CATEGORY
# ============================================================

class Category(Base):
    __tablename__ = "categories"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    name = Column(
        String(50),
        unique=True,
        nullable=False
    )

    description = Column(
        Text
    )

    items = relationship(
        "Product",
        back_populates="category"
    )


# ============================================================
# SUPPLIER
# ============================================================

class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    name = Column(
        String(100),
        nullable=False
    )

    contact_email = Column(
        String(120)
    )

    phone = Column(
        String(30)
    )

    address = Column(
        Text
    )

    products = relationship(
        "Product",
        back_populates="supplier"
    )

    # Purchases made from this supplier
    purchases = relationship(
        "Purchase",
        back_populates="supplier"
    )


# ============================================================
# PURCHASE
# ============================================================

class Purchase(Base):
    """
    Represents a purchase made from a supplier.

    A purchase can contain multiple products.
    When received, the products will be added to inventory
    and STOCK_IN transactions will be created.
    """

    __tablename__ = "purchases"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    supplier_id = Column(
        Integer,
        ForeignKey("suppliers.id"),
        nullable=False
    )

    location_id = Column(
        Integer,
        ForeignKey("locations.id"),
        nullable=False
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    purchase_number = Column(
        String(50),
        unique=True,
        index=True,
        nullable=False
    )

    invoice_number = Column(
        String(100),
        nullable=True
    )

    status = Column(
        Enum(PurchaseStatus),
        default=PurchaseStatus.DRAFT,
        nullable=False
    )

    subtotal = Column(
        Float,
        default=0.0,
        nullable=False
    )

    tax = Column(
        Float,
        default=0.0,
        nullable=False
    )

    total_amount = Column(
        Float,
        default=0.0,
        nullable=False
    )

    notes = Column(
        Text
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    received_at = Column(
        DateTime,
        nullable=True
    )

    # Relationships
    supplier = relationship(
        "Supplier",
        back_populates="purchases"
    )

    location = relationship(
        "Location",
        back_populates="purchases"
    )

    user = relationship(
        "User",
        back_populates="purchases"
    )

    items = relationship(
        "PurchaseItem",
        back_populates="purchase",
        cascade="all, delete-orphan"
    )


# ============================================================
# PURCHASE ITEM
# ============================================================

class PurchaseItem(Base):
    """
    Represents one product inside a purchase.
    """

    __tablename__ = "purchase_items"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    purchase_id = Column(
        Integer,
        ForeignKey(
            "purchases.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=False
    )

    quantity = Column(
        Integer,
        nullable=False
    )

    unit_cost = Column(
        Float,
        nullable=False
    )

    total_cost = Column(
        Float,
        nullable=False
    )

    purchase = relationship(
        "Purchase",
        back_populates="items"
    )

    product = relationship(
        "Product",
        back_populates="purchase_items"
    )


# ============================================================
# PRODUCT
# ============================================================

class Product(Base):
    __tablename__ = "products"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    sku = Column(
        String(50),
        unique=True,
        index=True,
        nullable=False
    )

    barcode = Column(
        String(100),
        unique=True,
        index=True,
        nullable=True
    )

    name = Column(
        String(200),
        nullable=False,
        index=True
    )

    description = Column(
        Text
    )

    category_id = Column(
        Integer,
        ForeignKey("categories.id")
    )

    supplier_id = Column(
        Integer,
        ForeignKey("suppliers.id")
    )

    unit_price = Column(
        Float,
        nullable=False,
        default=0.0
    )

    cost_price = Column(
        Float,
        nullable=False,
        default=0.0
    )

    reorder_level = Column(
        Integer,
        default=10
    )

    unit = Column(
        String(20),
        default="pcs"
    )

    image_path = Column(
        String(255)
    )

    is_active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships

    category = relationship(
        "Category",
        back_populates="items"
    )

    supplier = relationship(
        "Supplier",
        back_populates="products"
    )

    inventory_items = relationship(
        "InventoryItem",
        back_populates="product",
        cascade="all, delete-orphan"
    )

    transactions = relationship(
        "Transaction",
        back_populates="product"
    )

    purchase_items = relationship(
        "PurchaseItem",
        back_populates="product"
    )


# ============================================================
# INVENTORY ITEM
# ============================================================

class InventoryItem(Base):
    """
    Stores the quantity of a product at a specific location.
    """

    __tablename__ = "inventory_items"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=False
    )

    location_id = Column(
        Integer,
        ForeignKey("locations.id"),
        nullable=False
    )

    quantity = Column(
        Integer,
        default=0,
        nullable=False
    )

    reserved_quantity = Column(
        Integer,
        default=0
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    product = relationship(
        "Product",
        back_populates="inventory_items"
    )

    location = relationship(
        "Location",
        back_populates="inventory_items"
    )

    @property
    def available_quantity(self):
        return self.quantity - self.reserved_quantity


# ============================================================
# TRANSACTION
# ============================================================

class Transaction(Base):
    """
    Audit log for all inventory changes.
    """

    __tablename__ = "transactions"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=False
    )

    from_location_id = Column(
        Integer,
        ForeignKey("locations.id"),
        nullable=True
    )

    to_location_id = Column(
        Integer,
        ForeignKey("locations.id"),
        nullable=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    transaction_type = Column(
        Enum(TransactionType),
        nullable=False
    )

    quantity = Column(
        Integer,
        nullable=False
    )

    unit_price = Column(
        Float,
        default=0.0
    )

    total_amount = Column(
        Float,
        default=0.0
    )

    reference = Column(
        String(100)
    )

    notes = Column(
        Text
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    product = relationship(
        "Product",
        back_populates="transactions"
    )

    user = relationship(
        "User"
    )

    from_location = relationship(
        "Location",
        foreign_keys=[from_location_id]
    )

    to_location = relationship(
        "Location",
        foreign_keys=[to_location_id]
    )


# ============================================================
# PASSWORD RESET TOKEN
# ============================================================

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    token = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )

    expires_at = Column(
        DateTime,
        nullable=False
    )

    used = Column(
        String(10),
        default="false",
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)

    sale_number = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )

    location_id = Column(
        Integer,
        ForeignKey("locations.id"),
        nullable=False
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    subtotal = Column(Float, nullable=False, default=0.0)
    discount = Column(Float, nullable=False, default=0.0)
    tax = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False, default=0.0)

    payment_method = Column(
        String(30),
        nullable=False,
        default="cash"
    )

    amount_paid = Column(Float, nullable=False, default=0.0)
    change_amount = Column(Float, nullable=False, default=0.0)

    status = Column(
        String(20),
        nullable=False,
        default="completed"
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    items = relationship(
        "SaleItem",
        back_populates="sale",
        cascade="all, delete-orphan"
    )


class SaleItem(Base):
    __tablename__ = "sale_items"

    id = Column(Integer, primary_key=True, index=True)

    sale_id = Column(
        Integer,
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False
    )

    product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=False
    )

    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    unit_cost = Column(Float, nullable=False, default=0.0)
    total_price = Column(Float, nullable=False)

    sale = relationship(
        "Sale",
        back_populates="items"
    )

    product = relationship("Product")
