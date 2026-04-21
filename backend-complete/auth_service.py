"""
Minimal in-memory auth service for CLARIQ
Handles JWT tokens, user registration, and password hashing
No Snowflake dependency - pure Python
"""

import jwt
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# In-memory storage
USERS = {}  # {email: {user_id, email, password_hash, first_name, last_name, created_at}}
SESSIONS = {}  # {token: {user_id, created_at, expires_at}}
PASSWORD_RESETS = {}  # {token: {user_id, created_at, expires_at}}

class AuthService:
    """Minimal auth service with in-memory storage"""
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash password with salt"""
        salt = secrets.token_hex(32)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}${pwd_hash.hex()}"
    
    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        try:
            salt, pwd_hash = password_hash.split('$')
            new_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return new_hash.hex() == pwd_hash
        except:
            return False
    
    @staticmethod
    def create_user_email(email: str, password: str, first_name: str = "", last_name: str = "") -> Dict[str, Any]:
        """Create user with email/password"""
        if email in USERS:
            return {"error": "Email already registered"}
        
        user_id = secrets.token_urlsafe(16)
        password_hash = AuthService._hash_password(password)
        
        USERS[email] = {
            "user_id": user_id,
            "email": email,
            "password_hash": password_hash,
            "first_name": first_name,
            "last_name": last_name,
            "created_at": datetime.utcnow().isoformat()
        }
        
        return {
            "user_id": user_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "created_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_user_google(google_id: str, email: str, first_name: str = "", last_name: str = "") -> Dict[str, Any]:
        """Create or get user from Google OAuth"""
        # Check if user exists
        if email in USERS:
            user = USERS[email]
            return {
                "user_id": user["user_id"],
                "email": user["email"],
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "existing": True
            }
        
        # Create new user
        user_id = secrets.token_urlsafe(16)
        USERS[email] = {
            "user_id": user_id,
            "email": email,
            "password_hash": None,
            "google_id": google_id,
            "first_name": first_name,
            "last_name": last_name,
            "created_at": datetime.utcnow().isoformat()
        }
        
        return {
            "user_id": user_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "existing": False
        }
    
    @staticmethod
    def authenticate(email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with email/password"""
        if email not in USERS:
            return None
        
        user = USERS[email]
        if not user.get("password_hash"):
            return None
        
        if AuthService._verify_password(password, user["password_hash"]):
            return {
                "user_id": user["user_id"],
                "email": user["email"],
                "first_name": user["first_name"],
                "last_name": user["last_name"]
            }
        
        return None
    
    @staticmethod
    def create_session(user_id: str) -> Dict[str, str]:
        """Create JWT session for user"""
        payload = {
            "user_id": user_id,
            "iat": datetime.utcnow().timestamp(),
            "exp": (datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)).timestamp()
        }
        
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        SESSIONS[token] = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)).isoformat()
        }
        
        return {"token": token}
    
    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            
            # Check if session exists
            if token in SESSIONS:
                return payload
            
            return None
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    @staticmethod
    def logout(token: str) -> bool:
        """Invalidate session token"""
        if token in SESSIONS:
            del SESSIONS[token]
        return True
    
    @staticmethod
    def create_password_reset_token(email: str) -> Optional[str]:
        """Create password reset token"""
        if email not in USERS:
            return None
        
        user_id = USERS[email]["user_id"]
        reset_token = secrets.token_urlsafe(32)
        
        PASSWORD_RESETS[reset_token] = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
        }
        
        return reset_token
    
    @staticmethod
    def reset_password(reset_token: str, new_password: str) -> bool:
        """Reset password using token"""
        if reset_token not in PASSWORD_RESETS:
            return False
        
        reset_data = PASSWORD_RESETS[reset_token]
        user_id = reset_data["user_id"]
        
        # Find user by user_id and update password
        for email, user in USERS.items():
            if user["user_id"] == user_id:
                user["password_hash"] = AuthService._hash_password(new_password)
                del PASSWORD_RESETS[reset_token]
                return True
        
        return False
    
    @staticmethod
    def get_user(user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        for email, user in USERS.items():
            if user["user_id"] == user_id:
                return {
                    "user_id": user["user_id"],
                    "email": user["email"],
                    "first_name": user["first_name"],
                    "last_name": user["last_name"],
                    "created_at": user["created_at"]
                }
        return None
