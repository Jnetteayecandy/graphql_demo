from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
import jwt

from ..database import get_db
from ..models import UserDB
from ..schemas import UserCreate, UserResponse

router = APIRouter()

SECRET_KEY = "secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Cookie settings (Week: Cookie)
TOKEN_COOKIE = "access_token"   # httponly  -> JavaScript can NOT read it (safe from XSS)
USERNAME_COOKIE = "username"    # normal    -> JavaScript CAN read it (only for display)
COOKIE_MAX_AGE = ACCESS_TOKEN_EXPIRE_MINUTES * 60  # seconds, same lifetime as the JWT

# auto_error=False -> a missing "Authorization: Bearer" header is OK,
# because we can fall back to the cookie
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)
password_hash = PasswordHash.recommended()

blacklist = set()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(UserDB).filter(UserDB.username == user.username).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered",
        )

    db_user = UserDB(
        username=user.username,
        hashed_password=password_hash.hash(user.password),
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@router.post("/login")
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(UserDB).filter(UserDB.username == form_data.username).first()

    if not user or not password_hash.verify(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    token = jwt.encode(
        {"sub": user.username, "exp": expires},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    # The JWT is stored in an httponly cookie: the browser sends it automatically
    # with every request, but JavaScript (document.cookie) cannot read it.
    response.set_cookie(
        key=TOKEN_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        path="/",
    )
    # A normal cookie that the frontend is allowed to read (just the username).
    response.set_cookie(
        key=USERNAME_COOKIE,
        value=user.username,
        httponly=False,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        path="/",
    )

    # The token is NOT returned in the body any more - that is the whole point
    # of the httponly cookie (frontend JavaScript never touches the token).
    return {"message": "Logged in successfully", "username": user.username}


def get_token(
    bearer_token: Optional[str] = Depends(oauth2_scheme),
    access_token: Optional[str] = Cookie(default=None),
) -> str:
    """Read the JWT from the cookie, or from an Authorization: Bearer header (curl / Postman)."""
    token = access_token or bearer_token
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token


def get_current_user(token: str = Depends(get_token)) -> str:
    if token in blacklist:
        raise HTTPException(status_code=401, detail="Token has been revoked")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")

        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        return username
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/me")
async def me(username: str = Depends(get_current_user)):
    """Used by the frontend after a page refresh: 'am I still logged in?'"""
    return {"username": username}


@router.post("/logout")
async def logout(
    response: Response,
    bearer_token: Optional[str] = Depends(oauth2_scheme),
    access_token: Optional[str] = Cookie(default=None),
):
    token = access_token or bearer_token
    if token:
        blacklist.add(token)

    # Tell the browser to remove both cookies
    response.delete_cookie(TOKEN_COOKIE, path="/", httponly=True, samesite="lax")
    response.delete_cookie(USERNAME_COOKIE, path="/", samesite="lax")

    return {"message": "Logged out successfully"}
