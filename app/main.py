from fastapi import FastAPI

app = FastAPI(
    title="Inventory Management System",
    description="Inventory Management System API",
    version="1.0.0",
)


@app.get("/")
def root():
    return {
        "message": "Inventory Management System API is running",
        "status": "success"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }