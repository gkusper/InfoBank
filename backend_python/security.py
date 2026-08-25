import os
import datetime
import uuid
from pathlib import Path

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
TOKEN_ISSUER = os.getenv("JWT_ISSUER", "infobank-api")
TOKEN_AUDIENCE = os.getenv("JWT_AUDIENCE", "infobank-frontend")

if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is missing from backend_python/.env")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    try:
        ttl_seconds = int(os.getenv("JWT_ACCESS_TOKEN_TTL_SECONDS", "3600"))
    except ValueError as exc:
        raise RuntimeError("JWT_ACCESS_TOKEN_TTL_SECONDS must be an integer.") from exc
    if ttl_seconds < 60 or ttl_seconds > 86400:
        raise RuntimeError("JWT_ACCESS_TOKEN_TTL_SECONDS must be between 60 and 86400.")
    now = datetime.datetime.now(datetime.UTC)
    payload = dict(data)
    payload.update({
        "iat": now,
        "nbf": now,
        "exp": now + datetime.timedelta(seconds=ttl_seconds),
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "jti": str(uuid.uuid4()),
    })
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user_id(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            issuer=TOKEN_ISSUER,
            audience=TOKEN_AUDIENCE,
            options={"require": ["sub", "exp", "iat", "nbf", "iss", "aud", "jti"]},
        )
        user_id = payload.get("sub")
        if not isinstance(user_id, str) or not user_id:
            raise jwt.InvalidTokenError("Token subject is missing.")
        return user_id
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token invalid or expired.")
