"""
==============================================================================
Validation Utilities Module
==============================================================================

Production-grade validation classes for input data.

This module implements:
- RequestNameValidator: Validates pick request names
- UPCValidator: Validates product UPC codes

Validation Rules for Request Names:
----------------------------------
- Length: 3-50 characters
- Allowed: letters, numbers, underscore, hyphen
- Must start with a letter
- No spaces allowed
- Stored as lowercase

==============================================================================
"""

from __future__ import annotations

import re
from typing import Optional, Tuple


class RequestNameValidator:
    """
    Validator for pick request names.
    
    Validates request names against the following rules:
    - Length: 3-50 characters
    - Starts with a letter
    - Contains only alphanumeric, underscore, hyphen
    - No spaces
    
    Example:
        >>> validator = RequestNameValidator()
        >>> is_valid, normalized, error = validator.validate("Monday-Restock")
        >>> print(normalized)
        'monday-restock'
    """
    
    # Regex pattern for valid names
    PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{2,49}$")
    
    # Constraints
    MIN_LENGTH = 3
    MAX_LENGTH = 50
    
    def validate(self, name: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate and normalize a request name.
        
        Args:
            name: Raw request name input
            
        Returns:
            Tuple of (is_valid, normalized_name, error_message)
            - If valid: (True, "normalized-name", None)
            - If invalid: (False, None, "Error description")
        """
        if not name:
            return False, None, "Name is required"
        
        # Strip whitespace
        name = name.strip()
        
        # Check for spaces
        if " " in name:
            return False, None, "Name cannot contain spaces"
        
        # Check length
        if len(name) < self.MIN_LENGTH:
            return False, None, f"Name must be at least {self.MIN_LENGTH} characters"
        
        if len(name) > self.MAX_LENGTH:
            return False, None, f"Name must be at most {self.MAX_LENGTH} characters"
        
        # Check first character
        if not name[0].isalpha():
            return False, None, "Name must start with a letter"
        
        # Check pattern
        if not self.PATTERN.match(name):
            return False, None, "Name can only contain letters, numbers, underscores, and hyphens"
        
        # Normalize to lowercase
        normalized = name.lower()
        
        return True, normalized, None
    
    def is_valid(self, name: str) -> bool:
        """Quick validation check."""
        is_valid, _, _ = self.validate(name)
        return is_valid


class UPCValidator:
    """
    Validator for product UPC codes.
    
    Performs basic validation on UPC/barcode strings.
    """
    
    MIN_LENGTH = 4
    MAX_LENGTH = 20
    
    def validate(self, upc: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a UPC code.
        
        Args:
            upc: UPC string to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not upc:
            return False, "UPC is required"
        
        upc = upc.strip()
        
        if not upc:
            return False, "UPC cannot be empty"
        
        # Check alphanumeric
        if not upc.replace("-", "").isalnum():
            return False, "UPC must be alphanumeric"
        
        # Check length
        if len(upc) < self.MIN_LENGTH or len(upc) > self.MAX_LENGTH:
            return False, f"UPC must be {self.MIN_LENGTH}-{self.MAX_LENGTH} characters"
        
        return True, None
    
    def is_valid(self, upc: str) -> bool:
        """Quick validation check."""
        is_valid, _ = self.validate(upc)
        return is_valid


class QuantityValidator:
    """
    Validator for quantity values.
    """
    
    MAX_QUANTITY = 9999
    
    def validate(self, qty: int, max_qty: int = None) -> Tuple[bool, Optional[str]]:
        """
        Validate a quantity value.
        
        Args:
            qty: Quantity to validate
            max_qty: Maximum allowed (defaults to MAX_QUANTITY)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if max_qty is None:
            max_qty = self.MAX_QUANTITY
        
        if qty < 0:
            return False, "Quantity cannot be negative"
        
        if qty > max_qty:
            return False, f"Quantity cannot exceed {max_qty}"
        
        return True, None
