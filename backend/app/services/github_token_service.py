"""
GitHub token management service for OAuth token refresh.

Handles token validation, refresh, and automatic recovery from expired tokens.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import encrypt_token, decrypt_token
from app.models.models import User

logger = logging.getLogger(__name__)

# Buffer time before expiration to trigger refresh (5 minutes)
TOKEN_EXPIRY_BUFFER = timedelta(minutes=5)


class TokenRefreshError(Exception):
    """Raised when token refresh fails."""
    pass


class TokenInvalidError(Exception):
    """Raised when token is invalid and cannot be refreshed."""
    pass


async def validate_github_token(token: str) -> bool:
    """
    Validate a GitHub token by making an API call.

    Args:
        token: The GitHub access token to validate

    Returns:
        True if token is valid, False otherwise
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                timeout=10.0,
            )
            return response.status_code == 200
    except Exception as e:
        logger.error(f"[TOKEN] Error validating token: {e}")
        return False


async def refresh_github_token(refresh_token: str) -> Tuple[str, Optional[str], Optional[int]]:
    """
    Refresh a GitHub access token using the refresh token.

    Args:
        refresh_token: The refresh token from GitHub OAuth

    Returns:
        Tuple of (new_access_token, new_refresh_token, expires_in_seconds)

    Raises:
        TokenRefreshError: If refresh fails
    """
    logger.info("[TOKEN] Attempting to refresh GitHub token")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                headers={"Accept": "application/json"},
                timeout=30.0,
            )

            if response.status_code != 200:
                logger.error(f"[TOKEN] Refresh request failed with status {response.status_code}")
                raise TokenRefreshError(f"GitHub API returned status {response.status_code}")

            data = response.json()

            if "error" in data:
                error = data.get("error")
                error_desc = data.get("error_description", "Unknown error")
                logger.error(f"[TOKEN] GitHub refresh error: {error} - {error_desc}")
                raise TokenRefreshError(f"GitHub OAuth error: {error_desc}")

            new_access_token = data.get("access_token")
            if not new_access_token:
                raise TokenRefreshError("No access token in refresh response")

            # GitHub may issue a new refresh token
            new_refresh_token = data.get("refresh_token")
            expires_in = data.get("expires_in")  # Seconds until expiration

            logger.info(f"[TOKEN] Token refreshed successfully, expires_in={expires_in}s")
            return new_access_token, new_refresh_token, expires_in

    except httpx.RequestError as e:
        logger.error(f"[TOKEN] Network error during refresh: {e}")
        raise TokenRefreshError(f"Network error: {e}")


def is_token_expired(user: User) -> bool:
    """
    Check if the user's GitHub token is expired or about to expire.

    Args:
        user: The user model instance

    Returns:
        True if token is expired or will expire soon
    """
    if not user.github_token_expires_at:
        # No expiration tracked - token doesn't expire (classic PAT or OAuth without expiration)
        return False

    # Check if token expires within the buffer period
    expiry_threshold = datetime.utcnow() + TOKEN_EXPIRY_BUFFER
    return user.github_token_expires_at <= expiry_threshold


async def ensure_valid_token(
    user: User,
    db: AsyncSession,
    force_validate: bool = False,
) -> str:
    """
    Ensure the user has a valid GitHub token, refreshing if necessary.

    This is the main entry point for token management. It:
    1. Checks if the token is expired based on stored expiration
    2. If expired and refresh token exists, refreshes the token
    3. Optionally validates the token with GitHub API
    4. Returns the valid decrypted token

    Args:
        user: The user model instance
        db: Database session for updates
        force_validate: If True, validates token with GitHub even if not expired

    Returns:
        Valid decrypted GitHub access token

    Raises:
        TokenInvalidError: If token is invalid and cannot be refreshed
    """
    decrypted_token = decrypt_token(user.github_access_token)

    # Check if token needs refresh
    needs_refresh = is_token_expired(user)

    if needs_refresh:
        logger.info(f"[TOKEN] Token for user {user.username} is expired, attempting refresh")

        if not user.github_refresh_token:
            # No refresh token available - need to re-authenticate
            logger.warning(f"[TOKEN] No refresh token for user {user.username}, re-auth required")
            raise TokenInvalidError(
                "GitHub token has expired and no refresh token is available. "
                "Please re-authenticate with GitHub."
            )

        try:
            refresh_token = decrypt_token(user.github_refresh_token)
            new_token, new_refresh, expires_in = await refresh_github_token(refresh_token)

            # Update user's token in database
            user.github_access_token = encrypt_token(new_token)

            if new_refresh:
                user.github_refresh_token = encrypt_token(new_refresh)

            if expires_in:
                user.github_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            await db.commit()
            logger.info(f"[TOKEN] Updated token for user {user.username}")

            return new_token

        except TokenRefreshError as e:
            logger.error(f"[TOKEN] Failed to refresh token for user {user.username}: {e}")
            raise TokenInvalidError(
                f"Failed to refresh GitHub token: {e}. "
                "Please re-authenticate with GitHub."
            )

    # Token not expired - optionally validate
    if force_validate:
        is_valid = await validate_github_token(decrypted_token)
        if not is_valid:
            logger.warning(f"[TOKEN] Token validation failed for user {user.username}")

            # Try refresh if we have a refresh token
            if user.github_refresh_token:
                try:
                    refresh_token = decrypt_token(user.github_refresh_token)
                    new_token, new_refresh, expires_in = await refresh_github_token(refresh_token)

                    user.github_access_token = encrypt_token(new_token)
                    if new_refresh:
                        user.github_refresh_token = encrypt_token(new_refresh)
                    if expires_in:
                        user.github_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

                    await db.commit()
                    logger.info(f"[TOKEN] Recovered invalid token for user {user.username}")
                    return new_token

                except TokenRefreshError:
                    pass

            raise TokenInvalidError(
                "GitHub token is invalid. Please re-authenticate with GitHub."
            )

    return decrypted_token


async def handle_auth_failure(
    user: User,
    db: AsyncSession,
) -> Optional[str]:
    """
    Handle an authentication failure by attempting token refresh.

    Call this when a git operation fails with auth error.

    Args:
        user: The user model instance
        db: Database session for updates

    Returns:
        New valid token if refresh succeeded, None otherwise
    """
    logger.info(f"[TOKEN] Handling auth failure for user {user.username}")

    if not user.github_refresh_token:
        logger.warning(f"[TOKEN] No refresh token available for user {user.username}")
        return None

    try:
        refresh_token = decrypt_token(user.github_refresh_token)
        new_token, new_refresh, expires_in = await refresh_github_token(refresh_token)

        # Update user's token
        user.github_access_token = encrypt_token(new_token)
        if new_refresh:
            user.github_refresh_token = encrypt_token(new_refresh)
        if expires_in:
            user.github_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        await db.commit()
        logger.info(f"[TOKEN] Successfully recovered from auth failure for user {user.username}")

        return new_token

    except TokenRefreshError as e:
        logger.error(f"[TOKEN] Failed to recover from auth failure: {e}")
        return None
