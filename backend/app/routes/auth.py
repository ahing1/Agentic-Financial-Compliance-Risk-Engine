import logging

from fastapi import APIRouter, HTTPException

from app.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    TokenResponse,
)
from app.services.auth_service import register_user, authenticate_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=RegisterResponse)
def register(request: RegisterRequest):
    try:
        result = register_user(request.email, request.password)
        return RegisterResponse(
            user_id=result["user_id"],
            email=result["email"],
            message="Account created successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    """
    Authenticate and receive a JWT token.
    
    Include the token in subsequent requests:
    Authorization: Bearer <token>
    """
    try:
        result = authenticate_user(request.email, request.password)
        return TokenResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=500, detail="Login failed")