import hashlib
import base64
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import settings
from app.db.session import get_session
from app.models.user import User

logger = logging.getLogger(__name__)

def _prehash(password: str) -> bytes:
    """SHA-256 prehash to avoid bcrypt's 72-byte limit."""
    return base64.b64encode(
        hashlib.sha256(password.encode("utf-8")).digest()
    )

def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(_prehash(plain_password), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(_prehash(plain_password), hashed_password.encode("utf-8"))

def create_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=settings.jwt_expiration_hours)
    
    payload = {
        "sub": str(user_id),
        "exp": expires,
        "iat": now,
    }
    
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    
    logger.debug(f"Created token for user {user_id}, expires {expires}")
    return token

def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        
        user_id = payload.get("sub")
        if user_id is None:
            logger.warning("Token missing 'sub' claim")
            return None
        
        return user_id
        
    except JWTError as e:
        logger.warning(f"Token verification failed: {e}")
        return None
    

def register_user(email: str, password: str) -> dict:

    email = email.lower().strip()
    
    with get_session() as session:
        # Check if email already exists
        existing = session.query(User).filter_by(email=email).first()
        if existing:
            raise ValueError("Email already registered")
        
        # Create user with hashed password
        user = User(
            email=email,
            password_hash=hash_password(password),
        )
        session.add(user)
        session.commit()
        
        logger.info(f"Registered new user: {email}")
        
        return {
            "user_id": str(user.id),
            "email": user.email,
        }
    

def authenticate_user(email: str, password: str) -> dict:
    email = email.lower().strip()
    
    with get_session() as session:
        user = session.query(User).filter_by(email=email).first()
        
        if not user:
            # Don't reveal that the email doesn't exist
            raise ValueError("Invalid email or password")
        
        if not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")
        
        # Create JWT token
        token = create_token(str(user.id))
        
        logger.info(f"User authenticated: {email}")
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": str(user.id),
            "email": user.email,
        }