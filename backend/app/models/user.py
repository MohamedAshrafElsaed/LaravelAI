"""
User model module.

This module provides the User SQLAlchemy model for GitHub OAuth authentication.
The model is defined in models.py and re-exported here for cleaner imports.

Usage:
    from app.models.user import User
"""
from app.models.models import User

__all__ = ["User"]
