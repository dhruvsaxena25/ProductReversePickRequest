"""
==============================================================================
Security Module - Authentication & Cryptography
==============================================================================

Production-grade security management for JWT tokens and password hashing.

This module implements:
- SecurityManager: Singleton class for all security operations
- JWT token generation and verification
- Password hashing using bcrypt
- Token payload management

Design Patterns:
---------------
- Singleton: Single SecurityManager instance throughout application
- Factory Method: Token creation methods

Security Best Practices:
-----------------------
- Bcrypt for password hashing (adaptive, salted)
- JWT with configurable expiration
- Separate access and refresh tokens
- Token type validation to prevent misuse

Token Structure:
---------------
{
    "sub": "user-uuid",           # Subject (user ID)
    "username": "john",           # Username for convenience
    "role": "picker",             # User role
    "type": "access|refresh",     # Token type
    "exp": 1234567890,            # Expiration timestamp
    "iat": 1234567890             # Issued at timestamp
}

==============================================================================
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings


# Module logger
logger = logging.getLogger(__name__)


class SecurityManager:
    """
    Centralized security manager for authentication operations.
    
    This class handles all security-related operations including:
    - Password hashing and verification using bcrypt
    - JWT token generation (access and refresh)
    - Token verification and decoding
    
    The class is designed as a singleton to ensure consistent
    security configuration throughout the application.
    
    Attributes:
        _pwd_context: Passlib context for password hashing
        _settings: Application settings reference
    
    Example:
        >>> security = SecurityManager()
        >>> 
        >>> # Hash a password
        >>> hashed = security.hash_password("secret123")
        >>> 
        >>> # Verify password
        >>> is_valid = security.verify_password("secret123", hashed)
        >>> 
        >>> # Create tokens
        >>> access_token = security.create_access_token({"sub": "user-id"})
        >>> refresh_token = security.create_refresh_token({"sub": "user-id"})
        >>> 
        >>> # Verify token
        >>> payload = security.verify_token(access_token, "access")
    """
    
    # =========================================================================
    # CLASS CONSTANTS
    # =========================================================================
    
    # Token types for validation
    TOKEN_TYPE_ACCESS = "access"
    TOKEN_TYPE_REFRESH = "refresh"
    
    # Bcrypt configuration
    BCRYPT_SCHEMES = ["bcrypt"]
    BCRYPT_DEPRECATED = "auto"
    
    def __init__(self) -> None:
        """
        Initialize the security manager.
        
        Sets up the password hashing context and loads settings.
        """
        # Initialize password hashing context with bcrypt
        self._pwd_context = CryptContext(
            schemes=self.BCRYPT_SCHEMES,
            deprecated=self.BCRYPT_DEPRECATED
        )
        
        # Load settings reference
        self._settings = get_settings()
        
        logger.debug("SecurityManager initialized")
    
    # =========================================================================
    # PASSWORD HASHING METHODS
    # =========================================================================
    
    def hash_password(self, plain_password: str) -> str:
        """
        Hash a plain text password using bcrypt.
        
        Bcrypt automatically generates a random salt and includes it
        in the resulting hash. The hash is adaptive and can be configured
        for different work factors.
        
        Args:
            plain_password: The plain text password to hash
            
        Returns:
            Bcrypt hash string (includes algorithm, salt, and hash)
            
        Example:
            >>> security = SecurityManager()
            >>> hashed = security.hash_password("mypassword123")
            >>> print(hashed)
            '$2b$12$...'
        """
        if not plain_password:
            raise ValueError("Password cannot be empty")
        
        hashed = self._pwd_context.hash(plain_password)
        logger.debug("Password hashed successfully")
        return hashed
    
    def verify_password(
        self,
        plain_password: str,
        hashed_password: str
    ) -> bool:
        """
        Verify a plain text password against a bcrypt hash.
        
        This method is timing-safe to prevent timing attacks.
        
        Args:
            plain_password: The plain text password to verify
            hashed_password: The bcrypt hash to verify against
            
        Returns:
            True if password matches, False otherwise
            
        Example:
            >>> security = SecurityManager()
            >>> hashed = security.hash_password("secret")
            >>> security.verify_password("secret", hashed)
            True
            >>> security.verify_password("wrong", hashed)
            False
        """
        try:
            is_valid = self._pwd_context.verify(plain_password, hashed_password)
            
            if is_valid:
                logger.debug("Password verification successful")
            else:
                logger.debug("Password verification failed")
            
            return is_valid
            
        except Exception as e:
            # Log error but don't expose details
            logger.warning(f"Password verification error: {type(e).__name__}")
            return False
    
    # =========================================================================
    # JWT TOKEN CREATION METHODS
    # =========================================================================
    
    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT access token.
        
        Access tokens are short-lived and used for API authentication.
        They should be included in the Authorization header.
        
        Args:
            data: Payload data (must include 'sub' for user ID)
            expires_delta: Custom expiration time (optional)
            
        Returns:
            Encoded JWT access token string
            
        Example:
            >>> security = SecurityManager()
            >>> token = security.create_access_token({
            ...     "sub": "user-uuid",
            ...     "username": "john",
            ...     "role": "picker"
            ... })
        """
        return self._create_token(
            data=data,
            token_type=self.TOKEN_TYPE_ACCESS,
            expires_delta=expires_delta or timedelta(
                minutes=self._settings.access_token_expire_minutes
            )
        )
    
    def create_refresh_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT refresh token.
        
        Refresh tokens are long-lived and used to obtain new access tokens
        without re-authentication. They should be stored securely.
        
        Args:
            data: Payload data (must include 'sub' for user ID)
            expires_delta: Custom expiration time (optional)
            
        Returns:
            Encoded JWT refresh token string
            
        Example:
            >>> security = SecurityManager()
            >>> token = security.create_refresh_token({"sub": "user-uuid"})
        """
        return self._create_token(
            data=data,
            token_type=self.TOKEN_TYPE_REFRESH,
            expires_delta=expires_delta or timedelta(
                days=self._settings.refresh_token_expire_days
            )
        )
    
    def _create_token(
        self,
        data: Dict[str, Any],
        token_type: str,
        expires_delta: timedelta
    ) -> str:
        """
        Internal method to create a JWT token.
        
        This method handles the common logic for both access and refresh
        token creation.
        
        Args:
            data: Payload data to encode
            token_type: Type of token ('access' or 'refresh')
            expires_delta: Token expiration time
            
        Returns:
            Encoded JWT token string
        """
        # Create a copy to avoid modifying original data
        payload = data.copy()
        
        # Calculate expiration time
        now = datetime.now(timezone.utc)
        expire = now + expires_delta
        
        # Add standard claims
        payload.update({
            "type": token_type,
            "exp": expire,
            "iat": now
        })
        
        # Encode the token
        encoded_token = jwt.encode(
            payload,
            self._settings.jwt_secret_key,
            algorithm=self._settings.jwt_algorithm
        )
        
        logger.debug(
            f"Created {token_type} token, expires: {expire.isoformat()}"
        )
        
        return encoded_token
    
    # =========================================================================
    # JWT TOKEN VERIFICATION METHODS
    # =========================================================================
    
    def verify_token(
        self,
        token: str,
        token_type: str = TOKEN_TYPE_ACCESS
    ) -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT token.
        
        This method validates:
        - Token signature
        - Token expiration
        - Token type (access vs refresh)
        
        Args:
            token: The JWT token string to verify
            token_type: Expected token type ('access' or 'refresh')
            
        Returns:
            Decoded payload dictionary if valid, None otherwise
            
        Example:
            >>> security = SecurityManager()
            >>> token = security.create_access_token({"sub": "user-id"})
            >>> payload = security.verify_token(token, "access")
            >>> print(payload["sub"])
            'user-id'
        """
        try:
            # Decode and verify the token
            payload = jwt.decode(
                token,
                self._settings.jwt_secret_key,
                algorithms=[self._settings.jwt_algorithm]
            )
            
            # Validate token type
            if payload.get("type") != token_type:
                logger.warning(
                    f"Token type mismatch: expected {token_type}, "
                    f"got {payload.get('type')}"
                )
                return None
            
            logger.debug(f"Token verification successful: {token_type}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.debug("Token verification failed: token expired")
            return None
            
        except JWTError as e:
            logger.warning(f"Token verification failed: {e}")
            return None
    
    def decode_token_unsafe(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode a JWT token WITHOUT verification.
        
        WARNING: This method does not verify the signature or expiration.
        Only use for debugging or extracting non-sensitive information.
        
        Args:
            token: The JWT token string to decode
            
        Returns:
            Decoded payload dictionary, or None if decoding fails
        """
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret_key,
                algorithms=[self._settings.jwt_algorithm],
                options={"verify_signature": False, "verify_exp": False}
            )
            return payload
            
        except JWTError as e:
            logger.warning(f"Token decode failed: {e}")
            return None
    
    def get_token_expiry(self, token: str) -> Optional[datetime]:
        """
        Extract expiration time from a token.
        
        Args:
            token: The JWT token string
            
        Returns:
            Expiration datetime, or None if extraction fails
        """
        payload = self.decode_token_unsafe(token)
        
        if payload and "exp" in payload:
            return datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        
        return None
    
    def is_token_expired(self, token: str) -> bool:
        """
        Check if a token is expired.
        
        Args:
            token: The JWT token string
            
        Returns:
            True if expired or invalid, False if still valid
        """
        expiry = self.get_token_expiry(token)
        
        if expiry is None:
            return True
        
        return datetime.now(timezone.utc) >= expiry
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def get_access_token_expire_seconds(self) -> int:
        """Get access token expiration time in seconds."""
        return self._settings.access_token_expire_minutes * 60
    
    def get_refresh_token_expire_seconds(self) -> int:
        """Get refresh token expiration time in seconds."""
        return self._settings.refresh_token_expire_days * 24 * 60 * 60


# =============================================================================
# SINGLETON INSTANCE MANAGEMENT
# =============================================================================

@lru_cache(maxsize=1)
def get_security_manager() -> SecurityManager:
    """
    Get the global SecurityManager instance (singleton pattern).
    
    Uses lru_cache to ensure only one SecurityManager instance exists.
    This provides consistent security configuration and efficient
    password hashing context reuse.
    
    Returns:
        Global SecurityManager instance
        
    Example:
        >>> security = get_security_manager()
        >>> hashed = security.hash_password("secret")
    """
    return SecurityManager()


# =============================================================================
# CONVENIENCE FUNCTIONS (Backward Compatibility)
# =============================================================================

def hash_password(plain_password: str) -> str:
    """
    Convenience function to hash a password.
    
    Args:
        plain_password: Plain text password
        
    Returns:
        Bcrypt hash string
    """
    return get_security_manager().hash_password(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Convenience function to verify a password.
    
    Args:
        plain_password: Plain text password
        hashed_password: Bcrypt hash to verify against
        
    Returns:
        True if password matches
    """
    return get_security_manager().verify_password(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any]) -> str:
    """
    Convenience function to create an access token.
    
    Args:
        data: Payload data
        
    Returns:
        JWT access token string
    """
    return get_security_manager().create_access_token(data)


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Convenience function to create a refresh token.
    
    Args:
        data: Payload data
        
    Returns:
        JWT refresh token string
    """
    return get_security_manager().create_refresh_token(data)


def verify_token(
    token: str,
    token_type: str = SecurityManager.TOKEN_TYPE_ACCESS
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to verify a token.
    
    Args:
        token: JWT token string
        token_type: Expected token type
        
    Returns:
        Decoded payload or None
    """
    return get_security_manager().verify_token(token, token_type)
