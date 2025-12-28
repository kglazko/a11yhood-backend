"""Authentication and authorization services.

Provides token verification, user identity extraction, and role-based access control.
In TEST_MODE, accepts dev tokens for stable test identities without real OAuth.
Security: All authorization checks enforce server-side validation; never trust client roles.
"""
from fastapi import Header, HTTPException, Depends
from config import Settings, settings
from services.database import get_db, verify_token
from services.security_logger import log_auth_failure
from database_adapter import DatabaseAdapter

# Fixed dev identities shared with frontend src/lib/dev-users.ts
# Must match exactly between frontend and backend.
# Security: Only active when TEST_MODE=true; production uses real Supabase auth.
DEV_USER_IDS = {
    "49366adb-2d13-412f-9ae5-4c35dbffab10": "admin_user",
    "94e116f7-885d-4d32-87ae-697c5dc09b9e": "moderator_user",
    "2a3b7c3e-971b-4b42-9c8c-0f1843486c50": "regular_user",
}


async def get_current_user(authorization: str = Header(None)):
    """
    Get current user from Authorization header.
    
    Returns user dict with id, email, username, role on success.
    Raises HTTPException 401 if token is missing or invalid.
    
    In TEST_MODE (dev):
      - Accepts: "dev-token-<user_id>" or "Bearer dev-token-<user_id>"
      - Verifies user_id exists in database and returns user data with role
    
    In production (TEST_MODE=false):
      - Accepts: valid Supabase JWT
      - Calls verify_token() for Supabase validation
    
    Security: Always re-derives user identity server-side; never trusts client assertions.
    """
    from config import settings, load_settings_from_env
    # Use fresh settings so tests that patch env (e.g., startup security) don't
    # leave a stale cached TEST_MODE value that would disable dev tokens.
    settings = load_settings_from_env()
    from services.database import get_db as get_database_adapter
    
    if not authorization:
        log_auth_failure(None, "Missing authorization header")
        raise HTTPException(status_code=401, detail="No authorization header")
    
    # Strip "Bearer " prefix if present
    token = authorization.replace("Bearer ", "").strip()
    
    # Dev mode: Accept test tokens
    if settings.TEST_MODE and token.startswith("dev-token-"):
        user_id = token.replace("dev-token-", "").strip()
        
        # Verify user exists in database
        db = get_database_adapter()
        response = db.table("users").select("*").eq("id", user_id).execute()

        if response.data and len(response.data) > 0:
            user = response.data[0]
            return {
                "id": user["id"],
                "email": user.get("email"),
                "username": user.get("username"),
                "role": user.get("role", "user")
            }
        else:
            log_auth_failure(user_id, "Dev token user not found in database")
            raise HTTPException(
                status_code=401, 
                detail=f"Dev user {user_id} not found. Ensure database is seeded with test users."
            )
    
    # Production: Real Supabase auth
    db_adapter = get_database_adapter()
    user = verify_token(token, db_adapter)

    # Normalize user to dict shape expected by routers
    try:
        user_dict = {
            "id": getattr(user, "id", None) if hasattr(user, "id") else (user.get("id") if isinstance(user, dict) else None),
            "email": getattr(user, "email", None) if hasattr(user, "email") else (user.get("email") if isinstance(user, dict) else None),
            "username": None,
            "role": "user",
            "github_id": None,
        }
        meta = None
        if hasattr(user, "user_metadata"):
            meta = getattr(user, "user_metadata")
        elif isinstance(user, dict):
            meta = user.get("user_metadata")

        if isinstance(meta, dict):
            user_dict["username"] = meta.get("preferred_username") or meta.get("user_name") or user_dict["email"]
            user_dict["github_id"] = meta.get("provider_id") or meta.get("sub")

        if not user_dict["username"] and user_dict["email"]:
            user_dict["username"] = user_dict["email"].split("@")[0]

        from services.database import get_db as get_database_adapter
        db_adapter = get_database_adapter()
        if user_dict["id"]:
            response = db_adapter.table("users").select("*").eq("id", user_dict["id"]).execute()
            if response.data and len(response.data) > 0:
                row = response.data[0]
                user_dict["role"] = row.get("role", "user")
                user_dict["username"] = row.get("username") or user_dict["username"]
                user_dict["github_id"] = row.get("github_id") or user_dict["github_id"]

        return user_dict
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication normalization failed: {str(e)}")


async def get_current_user_optional(authorization: str = Header(None)):
    """
    Variant of get_current_user that returns None when no Authorization header is provided.
    Useful for public endpoints that optionally enforce ownership/visibility checks.
    
    In TEST_MODE, also returns None if dev token references non-existent user (for user creation).
    """
    if not authorization:
        return None
    try:
        return await get_current_user(authorization)
    except HTTPException as e:
        # In test mode, if dev user doesn't exist yet, return None (allows user creation)
        if settings.TEST_MODE and "not found" in str(e.detail):
            return None
        raise


# ----- Authorization policy helpers -----
def ensure_admin(current_user: dict):
    """
    Enforce admin-only access.
    
    Security: Server-side role check prevents privilege escalation.
    Raises 403 Forbidden if current_user lacks admin role.
    """
    from services.security_logger import log_unauthorized_access
    
    if not current_user or current_user.get("role") != "admin":
        log_unauthorized_access(
            current_user.get("id") if current_user else None,
            "admin",
            f"Attempted admin action with role: {current_user.get('role') if current_user else 'none'}"
        )
        raise HTTPException(status_code=403, detail="Admin access required")


def ensure_self_or_admin(current_user: dict, user_id: str):
    """
    Permit if editing own record or user is admin; else 403.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if current_user.get("id") != user_id and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")


def can_change_role(current_user: dict) -> bool:
    """
    Only admins may change roles.
    """
    return bool(current_user and current_user.get("role") == "admin")
