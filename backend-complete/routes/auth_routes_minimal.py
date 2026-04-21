"""
Minimal FastAPI auth routes for CLARIQ
No database dependency, pure Python JWT
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr
import os
import requests
from typing import Optional

from auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Request/Response models
class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    reset_token: str
    new_password: str

class GoogleAuthRequest(BaseModel):
    token: str

class AuthResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    user: Optional[dict] = None
    message: str = ""

def get_token_from_header(authorization: Optional[str] = Header(None)) -> str:
    """Extract token from Authorization header"""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]

@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignupRequest):
    """Sign up new user with email/password"""
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    user = AuthService.create_user_email(
        email=request.email,
        password=request.password,
        first_name=request.first_name,
        last_name=request.last_name
    )
    
    if "error" in user:
        raise HTTPException(status_code=400, detail=user["error"])
    
    session = AuthService.create_session(user["user_id"])
    
    return AuthResponse(
        success=True,
        token=session["token"],
        user=user,
        message="User created successfully"
    )

@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Login with email/password"""
    user = AuthService.authenticate(request.email, request.password)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    session = AuthService.create_session(user["user_id"])
    
    return AuthResponse(
        success=True,
        token=session["token"],
        user=user,
        message="Login successful"
    )

@router.post("/google", response_model=AuthResponse)
async def google_auth(request: GoogleAuthRequest):
    """Authenticate with Google OAuth token"""
    try:
        google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        
        response = requests.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={request.token}"
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Google token")
        
        token_data = response.json()
        
        if token_data.get("aud") != google_client_id:
            raise HTTPException(status_code=401, detail="Invalid token audience")
        
        google_id = token_data.get("sub")
        email = token_data.get("email")
        first_name = token_data.get("given_name", "")
        last_name = token_data.get("family_name", "")
        
        user = AuthService.create_user_google(
            google_id=google_id,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        
        session = AuthService.create_session(user["user_id"])
        
        message = "User created" if not user.get("existing") else "Login successful"
        
        return AuthResponse(
            success=True,
            token=session["token"],
            user=user,
            message=message
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout", response_model=AuthResponse)
async def logout(authorization: Optional[str] = Header(None)):
    """Logout (invalidate session)"""
    token = get_token_from_header(authorization)
    
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")
    
    AuthService.logout(token)
    
    return AuthResponse(
        success=True,
        message="Logged out successfully"
    )

@router.post("/password-reset", response_model=AuthResponse)
async def request_password_reset(request: PasswordResetRequest):
    """Request password reset"""
    reset_token = AuthService.create_password_reset_token(request.email)
    
    if not reset_token:
        return AuthResponse(
            success=True,
            message="If email exists, reset token has been sent"
        )
    
    return AuthResponse(
        success=True,
        message="Password reset token created",
        user={"reset_token": reset_token}
    )

@router.post("/password-reset-confirm", response_model=AuthResponse)
async def confirm_password_reset(request: PasswordResetConfirm):
    """Confirm password reset"""
    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    success = AuthService.reset_password(request.reset_token, request.new_password)
    
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    return AuthResponse(
        success=True,
        message="Password reset successful"
    )

@router.get("/me")
async def get_current_user(authorization: Optional[str] = Header(None)):
    """Get current user from token"""
    token = get_token_from_header(authorization)
    
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")
    
    payload = AuthService.verify_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user = AuthService.get_user(payload["user_id"])
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"success": True, "user": user}

@router.post("/verify-token")
async def verify_token(token: str):
    """Verify if token is valid"""
    payload = AuthService.verify_token(token)
    
    return {
        "valid": payload is not None,
        "user_id": payload.get("user_id") if payload else None
    }

@router.get("/health")
async def auth_health():
    """Health check"""
    return {"status": "ok", "service": "auth"}
