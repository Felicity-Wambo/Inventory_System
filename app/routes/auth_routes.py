from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
import secrets
import smtplib
from email.message import EmailMessage

from app.database import get_db
from app.models import User, UserRole, PasswordResetToken

from app.auth import (
    authenticate_user,
    create_access_token,
    hash_password,
    get_current_user,
    require_role
)

from app.config import get_settings


router = APIRouter(
    prefix="/api/auth",
    tags=["auth"]
)

settings = get_settings()


# =========================================================
# USER SCHEMAS
# =========================================================

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


# =========================================================
# LOGIN
# =========================================================

@router.post("/token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):

    user = authenticate_user(
        db,
        form_data.username,
        form_data.password
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is inactive"
        )

    user.last_login = datetime.utcnow()

    db.commit()

    token = create_access_token(
        {
            "sub": user.username,
            "role": user.role.value
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# =========================================================
# REGISTER
# =========================================================

@router.post(
    "/register",
    response_model=UserOut
)
async def register(
    data: UserCreate,
    db: Session = Depends(get_db),
    current: User = Depends(
        require_role(UserRole.ADMIN)
    )
):

    if db.query(User).filter(
        User.username == data.username
    ).first():

        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    if db.query(User).filter(
        User.email == data.email
    ).first():

        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(
            data.password
        ),
        full_name=data.full_name,
        role=data.role
    )

    db.add(user)

    db.commit()

    db.refresh(user)

    return user


# =========================================================
# CURRENT USER
# =========================================================

@router.get(
    "/me",
    response_model=UserOut
)
async def me(
    current: User = Depends(get_current_user)
):

    return current


# =========================================================
# PASSWORD RESET SCHEMAS
# =========================================================

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


# =========================================================
# SEND RESET EMAIL
# =========================================================

def send_reset_email(
    email: str,
    reset_link: str
):
    """
    Sends a password-reset email through Gmail SMTP.

    Uses:
        smtp.gmail.com
        port 587
        STARTTLS
    """

    smtp_host = settings.SMTP_HOST
    smtp_port = settings.SMTP_PORT
    smtp_username = settings.SMTP_USERNAME
    smtp_password = settings.SMTP_PASSWORD

    from_email = (
        settings.SMTP_FROM_EMAIL
        or smtp_username
    )

    # -----------------------------------------------------
    # Validate configuration
    # -----------------------------------------------------

    if not smtp_host:
        raise RuntimeError(
            "SMTP_HOST is not configured."
        )

    if not smtp_port:
        raise RuntimeError(
            "SMTP_PORT is not configured."
        )

    if not smtp_username:
        raise RuntimeError(
            "SMTP_USERNAME is not configured."
        )

    if not smtp_password:
        raise RuntimeError(
            "SMTP_PASSWORD is not configured."
        )

    if not from_email:
        raise RuntimeError(
            "SMTP_FROM_EMAIL is not configured."
        )

    # -----------------------------------------------------
    # Create email
    # -----------------------------------------------------

    message = EmailMessage()

    message["Subject"] = (
        "Inventory Management System - Password Reset"
    )

    message["From"] = from_email

    message["To"] = email

    message.set_content(
        f"""
Hello,

We received a request to reset the password for your
Inventory Management System account.

Click the link below to create a new password:

{reset_link}

This link will expire in 30 minutes.

If you did not request a password reset, you can safely
ignore this email.

Regards,

Inventory Management System
"""
    )

    # -----------------------------------------------------
    # Send email
    # -----------------------------------------------------

    server = None

    try:

        print(
            f"Connecting to SMTP server "
            f"{smtp_host}:{smtp_port}..."
        )

        server = smtplib.SMTP(
            smtp_host,
            smtp_port,
            timeout=30
        )

        server.ehlo()

        print("SMTP connection established.")

        server.starttls()

        server.ehlo()

        print("SMTP TLS connection established.")

        server.login(
            smtp_username,
            smtp_password
        )

        print("SMTP authentication successful.")

        server.send_message(message)

        print(
            f"PASSWORD RESET EMAIL SENT TO: "
            f"{email}"
        )

    except smtplib.SMTPAuthenticationError as error:

        print(
            "SMTP AUTHENTICATION ERROR:",
            error
        )

        raise RuntimeError(
            "SMTP authentication failed. "
            "Check your Gmail address and App Password."
        )

    except smtplib.SMTPConnectError as error:

        print(
            "SMTP CONNECTION ERROR:",
            error
        )

        raise RuntimeError(
            "Unable to connect to the email server."
        )

    except smtplib.SMTPException as error:

        print(
            "SMTP ERROR:",
            error
        )

        raise RuntimeError(
            f"SMTP error: {error}"
        )

    except Exception as error:

        print(
            "EMAIL SENDING ERROR:",
            error
        )

        raise RuntimeError(
            f"Email sending failed: {error}"
        )

    finally:

        if server is not None:

            try:
                server.quit()

            except Exception:
                pass


# =========================================================
# FORGOT PASSWORD
# =========================================================

@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.email == data.email
    ).first()

    # -----------------------------------------------------
    # Do not reveal whether email exists
    # -----------------------------------------------------

    if not user:

        return {
            "message":
                "If an account exists with that email, "
                "a password reset link has been sent."
        }

    # -----------------------------------------------------
    # Delete previous unused tokens
    # -----------------------------------------------------

    db.query(
        PasswordResetToken
    ).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used == "false"
    ).delete(
        synchronize_session=False
    )

    # -----------------------------------------------------
    # Generate secure token
    # -----------------------------------------------------

    token = secrets.token_urlsafe(48)

    # -----------------------------------------------------
    # Token expiration
    # -----------------------------------------------------

    expires_at = (
        datetime.utcnow()
        + timedelta(minutes=30)
    )

    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
        used="false"
    )

    db.add(reset_token)

    db.commit()

    # -----------------------------------------------------
    # Create reset link
    # -----------------------------------------------------

    reset_link = (
        f"{settings.APP_BASE_URL}"
        f"/reset-password?token={token}"
    )

    # -----------------------------------------------------
    # Send email
    # -----------------------------------------------------

    try:

        send_reset_email(
            str(user.email),
            reset_link
        )

    except Exception as error:

        print(
            "PASSWORD RESET EMAIL ERROR:",
            error
        )

        # Remove token because email was not sent
        db.delete(reset_token)

        db.commit()

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to send password reset email. "
                "Please try again later."
            )
        )

    # -----------------------------------------------------
    # Success
    # -----------------------------------------------------

    return {
        "message":
            "If an account exists with that email, "
            "a password reset link has been sent."
    }


# =========================================================
# RESET PASSWORD
# =========================================================

@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):

    # -----------------------------------------------------
    # Find token
    # -----------------------------------------------------

    reset_token = db.query(
        PasswordResetToken
    ).filter(
        PasswordResetToken.token == data.token,
        PasswordResetToken.used == "false"
    ).first()

    if not reset_token:

        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset link."
        )

    # -----------------------------------------------------
    # Check expiration
    # -----------------------------------------------------

    if datetime.utcnow() > reset_token.expires_at:

        reset_token.used = "true"

        db.commit()

        raise HTTPException(
            status_code=400,
            detail="This reset link has expired."
        )

    # -----------------------------------------------------
    # Validate password
    # -----------------------------------------------------

    if len(data.password) < 8:

        raise HTTPException(
            status_code=400,
            detail=(
                "Password must contain "
                "at least 8 characters."
            )
        )

    # -----------------------------------------------------
    # Find user
    # -----------------------------------------------------

    user = db.query(User).filter(
        User.id == reset_token.user_id
    ).first()

    if not user:

        raise HTTPException(
            status_code=400,
            detail="User account no longer exists."
        )

    # -----------------------------------------------------
    # Change password
    # -----------------------------------------------------

    user.hashed_password = hash_password(
        data.password
    )

    # -----------------------------------------------------
    # Invalidate reset token
    # -----------------------------------------------------

    reset_token.used = "true"

    db.commit()

    return {
        "message":
            "Password reset successfully."
    }