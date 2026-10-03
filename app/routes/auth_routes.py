# app/routes/auth_routes.py
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.models import User, UserRole
from app.auth import (
    authenticate_user, create_access_token, hash_password,
    get_current_user, require_role
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str = ""
    role: UserRole = UserRole.STAFF


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    
    class Config:
        from_attributes = True


@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    user.last_login = datetime.utcnow()
    db.commit()
    token = create_access_token({"sub": user.username, "role": user.role.value})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/register", response_model=UserOut)
async def register(
    data: UserCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_role(UserRole.ADMIN)),
):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(400, "Username already exists")
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=UserOut)
async def me(current: User = Depends(get_current_user)):
    return current