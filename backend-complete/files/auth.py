from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
import hashlib
import secrets
import os
import jwt
import json

router = APIRouter()
security = HTTPBearer(auto_error=False)

# In-memory user store (move to database later)
users_db = {}

JWT_SECRET = os.getenv("JWT_SECRET", "clariq-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 72


# ═══ MODELS ═══

class SignupRequest(BaseModel):
    email: str
    password: str
    full_name: str
    company_name: Optional[str] = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleAuthRequest(BaseModel):
    token: str
    email: str
    name: str
    picture: Optional[str] = ""


class TokenVerifyRequest(BaseModel):
    token: str


# ═══ HELPERS ═══

def hash_password(password: str) -> str:
    salt = "clariq_salt_2026"
    return hashlib.sha256(f"{password}{salt}".encode()).hexdigest()


def create_jwt(user_id: str, email: str, name: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "name": name,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token. Please log in again.")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    token = credentials.credentials
    payload = decode_jwt(token)
    email = payload.get("email")
    if email not in users_db:
        raise HTTPException(status_code=401, detail="User not found. Please sign up.")
    return users_db[email]


# ═══ ENDPOINTS ═══

@router.post("/auth/signup")
async def signup(req: SignupRequest):
    """Create a new account with email and password."""
    email = req.email.lower().strip()

    if email in users_db:
        raise HTTPException(status_code=400, detail="An account with this email already exists. Try logging in.")

    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    user_id = f"user_{secrets.token_hex(8)}"

    user = {
        "user_id": user_id,
        "email": email,
        "full_name": req.full_name,
        "company_name": req.company_name,
        "password_hash": hash_password(req.password),
        "auth_method": "email",
        "picture": "",
        "created_at": datetime.utcnow().isoformat(),
        "connected_stores": [],
    }

    users_db[email] = user

    token = create_jwt(user_id, email, req.full_name)

    return {
        "message": f"Welcome to CLARIQ, {req.full_name}!",
        "token": token,
        "user": {
            "user_id": user_id,
            "email": email,
            "full_name": req.full_name,
            "company_name": req.company_name,
            "picture": "",
            "auth_method": "email",
        }
    }


@router.post("/auth/login")
async def login(req: LoginRequest):
    """Log in with email and password."""
    email = req.email.lower().strip()

    if email not in users_db:
        raise HTTPException(status_code=401, detail="No account found with this email. Please sign up first.")

    user = users_db[email]

    if user.get("auth_method") == "google":
        raise HTTPException(status_code=400, detail="This account uses Google sign-in. Please use 'Sign in with Google' instead.")

    if user["password_hash"] != hash_password(req.password):
        raise HTTPException(status_code=401, detail="Incorrect password. Please try again.")

    token = create_jwt(user["user_id"], email, user["full_name"])

    return {
        "message": f"Welcome back, {user['full_name']}!",
        "token": token,
        "user": {
            "user_id": user["user_id"],
            "email": email,
            "full_name": user["full_name"],
            "company_name": user.get("company_name", ""),
            "picture": user.get("picture", ""),
            "auth_method": "email",
        }
    }


@router.post("/auth/google")
async def google_auth(req: GoogleAuthRequest):
    """Sign in or sign up with Google. Frontend sends the Google user info after OAuth."""
    email = req.email.lower().strip()

    if email in users_db:
        # Existing user — log them in
        user = users_db[email]
        user["picture"] = req.picture or user.get("picture", "")
        token = create_jwt(user["user_id"], email, user["full_name"])

        return {
            "message": f"Welcome back, {user['full_name']}!",
            "token": token,
            "user": {
                "user_id": user["user_id"],
                "email": email,
                "full_name": user["full_name"],
                "company_name": user.get("company_name", ""),
                "picture": user.get("picture", ""),
                "auth_method": user.get("auth_method", "google"),
            }
        }
    else:
        # New user — create account
        user_id = f"user_{secrets.token_hex(8)}"

        user = {
            "user_id": user_id,
            "email": email,
            "full_name": req.name,
            "company_name": "",
            "password_hash": "",
            "auth_method": "google",
            "picture": req.picture or "",
            "created_at": datetime.utcnow().isoformat(),
            "connected_stores": [],
        }

        users_db[email] = user

        token = create_jwt(user_id, email, req.name)

        return {
            "message": f"Welcome to CLARIQ, {req.name}! Your account has been created.",
            "token": token,
            "user": {
                "user_id": user_id,
                "email": email,
                "full_name": req.name,
                "company_name": "",
                "picture": req.picture or "",
                "auth_method": "google",
            }
        }


@router.get("/auth/me")
async def get_me(user=Depends(get_current_user)):
    """Get the current logged-in user's info. Requires Bearer token."""
    return {
        "user": {
            "user_id": user["user_id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "company_name": user.get("company_name", ""),
            "picture": user.get("picture", ""),
            "auth_method": user.get("auth_method", ""),
            "created_at": user.get("created_at", ""),
        }
    }


@router.post("/auth/verify-token")
async def verify_token(req: TokenVerifyRequest):
    """Verify if a JWT token is still valid."""
    try:
        payload = decode_jwt(req.token)
        return {
            "valid": True,
            "email": payload.get("email"),
            "name": payload.get("name"),
            "expires_at": datetime.fromtimestamp(payload.get("exp", 0)).isoformat(),
        }
    except HTTPException:
        return {"valid": False}
