"""
Auth database module for CLARIQ
Handles user creation, JWT tokens, password hashing, and session management
"""

import jwt
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-super-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

class AuthDB:
    """Manages authentication with Snowflake backend"""
    
    def __init__(self):
        self.conn = None
        self.cursor = None
        self._connect()
    
    def _connect(self):
        """Connect to Snowflake"""
        try:
            self.conn = snowflake.connector.connect(
                account=os.getenv("SNOWFLAKE_ACCOUNT"),
                user=os.getenv("SNOWFLAKE_USER"),
                password=os.getenv("SNOWFLAKE_PASSWORD"),
                warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
                database=os.getenv("SNOWFLAKE_DATABASE"),
                schema=os.getenv("SNOWFLAKE_SCHEMA")
            )
            self.cursor = self.conn.cursor()
            self._create_auth_tables()
        except Exception as e:
            print(f"Snowflake connection failed: {e}")
            raise
    
    def _create_auth_tables(self):
        """Create auth tables if they don't exist"""
        try:
            # Users table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS AUTH_USERS (
                    user_id STRING PRIMARY KEY DEFAULT UUID_STRING(),
                    email STRING UNIQUE NOT NULL,
                    password_hash STRING,
                    google_id STRING UNIQUE,
                    first_name STRING,
                    last_name STRING,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)
            
            # Sessions table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS AUTH_SESSIONS (
                    session_id STRING PRIMARY KEY DEFAULT UUID_STRING(),
                    user_id STRING NOT NULL,
                    token STRING NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                    expires_at TIMESTAMP NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (user_id) REFERENCES AUTH_USERS(user_id)
                )
            """)
            
            # Password reset tokens
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS PASSWORD_RESETS (
                    reset_id STRING PRIMARY KEY DEFAULT UUID_STRING(),
                    user_id STRING NOT NULL,
                    token STRING NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                    expires_at TIMESTAMP NOT NULL,
                    is_used BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (user_id) REFERENCES AUTH_USERS(user_id)
                )
            """)
            
            self.conn.commit()
        except Exception as e:
            if "already exists" not in str(e):
                print(f"Error creating auth tables: {e}")
    
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
    
    def create_user_email(self, email: str, password: str, first_name: str = "", last_name: str = "") -> Dict[str, Any]:
        """Create user with email/password"""
        try:
            password_hash = self._hash_password(password)
            
            self.cursor.execute("""
                INSERT INTO AUTH_USERS (email, password_hash, first_name, last_name)
                VALUES (%s, %s, %s, %s)
                RETURNING user_id, email, first_name, last_name, created_at
            """, (email, password_hash, first_name, last_name))
            
            result = self.cursor.fetchone()
            self.conn.commit()
            
            if result:
                return {
                    "user_id": result[0],
                    "email": result[1],
                    "first_name": result[2],
                    "last_name": result[3],
                    "created_at": str(result[4])
                }
            return None
        except Exception as e:
            self.conn.rollback()
            if "already exists" in str(e).lower():
                return {"error": "Email already registered"}
            return {"error": str(e)}
    
    def create_user_google(self, google_id: str, email: str, first_name: str = "", last_name: str = "") -> Dict[str, Any]:
        """Create or get user from Google OAuth"""
        try:
            # Check if user exists
            self.cursor.execute("""
                SELECT user_id, email, first_name, last_name FROM AUTH_USERS 
                WHERE google_id = %s OR email = %s
            """, (google_id, email))
            
            result = self.cursor.fetchone()
            if result:
                return {
                    "user_id": result[0],
                    "email": result[1],
                    "first_name": result[2],
                    "last_name": result[3],
                    "existing": True
                }
            
            # Create new user
            self.cursor.execute("""
                INSERT INTO AUTH_USERS (google_id, email, first_name, last_name)
                VALUES (%s, %s, %s, %s)
                RETURNING user_id, email, first_name, last_name
            """, (google_id, email, first_name, last_name))
            
            result = self.cursor.fetchone()
            self.conn.commit()
            
            if result:
                return {
                    "user_id": result[0],
                    "email": result[1],
                    "first_name": result[2],
                    "last_name": result[3],
                    "existing": False
                }
            return None
        except Exception as e:
            self.conn.rollback()
            return {"error": str(e)}
    
    def authenticate(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with email/password"""
        try:
            self.cursor.execute("""
                SELECT user_id, email, password_hash, first_name, last_name 
                FROM AUTH_USERS WHERE email = %s AND is_active = TRUE
            """, (email,))
            
            result = self.cursor.fetchone()
            if not result:
                return None
            
            user_id, db_email, password_hash, first_name, last_name = result
            if self._verify_password(password, password_hash):
                return {
                    "user_id": user_id,
                    "email": db_email,
                    "first_name": first_name,
                    "last_name": last_name
                }
            return None
        except Exception as e:
            print(f"Auth error: {e}")
            return None
    
    def create_session(self, user_id: str) -> Dict[str, str]:
        """Create JWT session for user"""
        try:
            payload = {
                "user_id": user_id,
                "iat": datetime.utcnow().timestamp(),
                "exp": (datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)).timestamp()
            }
            
            token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
            
            self.cursor.execute("""
                INSERT INTO AUTH_SESSIONS (user_id, token, expires_at)
                VALUES (%s, %s, %s)
                RETURNING session_id
            """, (user_id, token, datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)))
            
            result = self.cursor.fetchone()
            self.conn.commit()
            
            return {"token": token, "session_id": result[0] if result else None}
        except Exception as e:
            self.conn.rollback()
            return {"error": str(e)}
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            
            # Check if session exists and is active
            self.cursor.execute("""
                SELECT user_id FROM AUTH_SESSIONS 
                WHERE token = %s AND is_active = TRUE AND expires_at > CURRENT_TIMESTAMP()
            """, (token,))
            
            if self.cursor.fetchone():
                return payload
            return None
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def logout(self, token: str) -> bool:
        """Invalidate session token"""
        try:
            self.cursor.execute("""
                UPDATE AUTH_SESSIONS SET is_active = FALSE WHERE token = %s
            """, (token,))
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"Logout error: {e}")
            return False
    
    def create_password_reset_token(self, email: str) -> Optional[str]:
        """Create password reset token"""
        try:
            self.cursor.execute("""
                SELECT user_id FROM AUTH_USERS WHERE email = %s AND is_active = TRUE
            """, (email,))
            
            result = self.cursor.fetchone()
            if not result:
                return None
            
            user_id = result[0]
            reset_token = secrets.token_urlsafe(32)
            
            self.cursor.execute("""
                INSERT INTO PASSWORD_RESETS (user_id, token, expires_at)
                VALUES (%s, %s, %s)
            """, (user_id, reset_token, datetime.utcnow() + timedelta(hours=1)))
            
            self.conn.commit()
            return reset_token
        except Exception as e:
            self.conn.rollback()
            print(f"Reset token error: {e}")
            return None
    
    def reset_password(self, reset_token: str, new_password: str) -> bool:
        """Reset password using token"""
        try:
            self.cursor.execute("""
                SELECT user_id FROM PASSWORD_RESETS 
                WHERE token = %s AND is_used = FALSE AND expires_at > CURRENT_TIMESTAMP()
            """, (reset_token,))
            
            result = self.cursor.fetchone()
            if not result:
                return False
            
            user_id = result[0]
            password_hash = self._hash_password(new_password)
            
            self.cursor.execute("""
                UPDATE AUTH_USERS SET password_hash = %s WHERE user_id = %s
            """, (password_hash, user_id))
            
            self.cursor.execute("""
                UPDATE PASSWORD_RESETS SET is_used = TRUE WHERE token = %s
            """, (reset_token,))
            
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"Password reset error: {e}")
            return False
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            self.cursor.execute("""
                SELECT user_id, email, first_name, last_name, created_at 
                FROM AUTH_USERS WHERE user_id = %s AND is_active = TRUE
            """, (user_id,))
            
            result = self.cursor.fetchone()
            if result:
                return {
                    "user_id": result[0],
                    "email": result[1],
                    "first_name": result[2],
                    "last_name": result[3],
                    "created_at": str(result[4])
                }
            return None
        except Exception as e:
            print(f"Get user error: {e}")
            return None
    
    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
