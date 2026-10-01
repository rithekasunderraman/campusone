from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..auth import verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token({"sub": user.username, "role": user.role})
    return schemas.TokenResponse(access_token=token, role=user.role,
                                  full_name=user.full_name, username=user.username)


@router.get("/me")
def me(current_user: models.User = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "email": current_user.email,
    }
