# init_db.py
from app.database import SessionLocal, Base, engine
from app.models import User, Location, Category, UserRole
from app.auth import hash_password

Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Admin user
if not db.query(User).filter_by(username="admin").first():
    admin = User(
        username="admin",
        email="admin@example.com",
        hashed_password=hash_password("admin123"),
        full_name="System Admin",
        role=UserRole.ADMIN,
    )
    db.add(admin)
    print("✓ Created admin user (username: admin, password: admin123)")

# Manager
if not db.query(User).filter_by(username="manager").first():
    mgr = User(
        username="manager",
        email="manager@example.com",
        hashed_password=hash_password("manager123"),
        full_name="Store Manager",
        role=UserRole.MANAGER,
    )
    db.add(mgr)
    print("✓ Created manager user (username: manager, password: manager123)")

# Locations
locations = [
    ("MAIN", "Main Warehouse", "123 Main St"),
    ("STORE1", "Downtown Store", "456 Oak Ave"),
    ("STORE2", "Uptown Store", "789 Elm Blvd"),
]
for code, name, addr in locations:
    if not db.query(Location).filter_by(code=code).first():
        db.add(Location(code=code, name=name, address=addr))
        print(f"✓ Created location: {code}")

# Categories
categories = ["Electronics", "Clothing", "Food", "Tools", "Other"]
for c in categories:
    if not db.query(Category).filter_by(name=c).first():
        db.add(Category(name=c))

db.commit()
db.close()
print("\n✓ Database initialized successfully!")