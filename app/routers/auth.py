from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AuthIn, RefreshIn, TokenPair
from app.services.auth import login_user, logout_session, refresh_session, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenPair, status_code=201)
def register(body: AuthIn, db: Session = Depends(get_db)) -> TokenPair:
    return register_user(db, body.email, body.password)


@router.post("/login", response_model=TokenPair)
def login(body: AuthIn, db: Session = Depends(get_db)) -> TokenPair:
    return login_user(db, body.email, body.password)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshIn, db: Session = Depends(get_db)) -> TokenPair:
    return refresh_session(db, body.refresh_token)


@router.post("/logout", status_code=204)
def logout(body: RefreshIn, db: Session = Depends(get_db)) -> None:
    logout_session(db, body.refresh_token)
