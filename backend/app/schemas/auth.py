import re

from pydantic import BaseModel, Field, field_validator

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


class RegisterRequest(BaseModel):
    """Request body for POST /auth/register"""
    email: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="Email address",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (minimum 8 characters)",
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.lower().strip()
        if not EMAIL_REGEX.match(v):
            raise ValueError("Please enter a valid email address")
        local, domain = v.split("@")
        if ".." in local or ".." in domain:
            raise ValueError("Please enter a valid email address")
        return v
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if v.isdigit():
            raise ValueError("Password cannot be all numbers")
        if v.isalpha():
            raise ValueError("Password must contain at least one number or special character")
        return v


class LoginRequest(BaseModel):
    """Request body for POST /auth/login"""
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """Response for POST /auth/login"""
    access_token: str
    token_type: str
    user_id: str
    email: str


class RegisterResponse(BaseModel):
    """Response for POST /auth/register"""
    user_id: str
    email: str
    message: str