from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
JWT_SECRET = os.getenv("JWT_SECRET", "clariq-jwt-secret-twotwentyone-2026-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# In-memory user store (replace with database later)
users_db = {}


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str = "User"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    google_id_token: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    email: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    first_name: str
    created_at: str


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_jwt_token(user_id: str, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignupRequest):
    """Sign up with email and password."""
    # Check if user already exists
    if request.email in users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Validate password strength
    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )
    
    # Create user
    user_id = f"user_{len(users_db) + 1}"
    hashed_pwd = hash_password(request.password)
    
    users_db[request.email] = {
        "user_id": user_id,
        "email": request.email,
        "password_hash": hashed_pwd,
        "first_name": request.first_name,
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Create token
    token = create_jwt_token(user_id, request.email)
    
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user_id=user_id,
        email=request.email
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Login with email and password."""
    # Check if user exists
    if request.email not in users_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    user = users_db[request.email]
    
    # Verify password
    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create token
    token = create_jwt_token(user["user_id"], user["email"])
    
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user_id=user["user_id"],
        email=user["email"]
    )


@router.post("/google")
async def google_auth(request: GoogleAuthRequest):
    """Authenticate with Google OAuth token."""
    # TODO: Verify Google ID token with Google's API
    # For now, return placeholder
    raise HTTPException(
        status_code=501,
        detail="Google OAuth coming soon"
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(token: str = None):
    """Get current authenticated user."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No token provided"
        )
    
    payload = verify_jwt_token(token)
    user_id = payload.get("user_id")
    email = payload.get("email")
    
    # Find user by ID
    for user_email, user_data in users_db.items():
        if user_data["user_id"] == user_id:
            return UserResponse(
                user_id=user_id,
                email=email,
                first_name=user_data["first_name"],
                created_at=user_data["created_at"]
            )
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="User not found"
    )


@router.post("/verify-token")
async def verify_token(token: str):
    """Verify a JWT token."""
    payload = verify_jwt_token(token)
    return {
        "valid": True,
        "user_id": payload.get("user_id"),
        "email": payload.get("email"),
        "expires_at": payload.get("exp")
    }
