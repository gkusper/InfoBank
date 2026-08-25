import re

from pydantic import BaseModel, constr, validator

class UserRegister(BaseModel):
    email: constr(strip_whitespace=True, min_length=3, max_length=255)
    username: constr(strip_whitespace=True, min_length=3, max_length=100, regex=r"^[A-Za-z0-9_.-]+$")
    password: constr(min_length=12, max_length=128)

    @validator("email")
    def validate_email_shape(cls, value: str) -> str:
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("A valid email address is required.")
        return value.lower()

class UserLogin(BaseModel):
    email: constr(strip_whitespace=True, min_length=3, max_length=255)
    password: constr(min_length=1, max_length=128)

class ProfileUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
