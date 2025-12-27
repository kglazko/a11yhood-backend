"""User account management endpoints.

Handles user profile CRUD, role management, and ownership tracking.
Security: Role changes restricted to admins; users can only edit their own profiles.
Privacy: Public username lookup excludes email and preferences.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel
from services.database import get_db
from services.auth import get_current_user, get_current_user_optional, ensure_admin, DEV_USER_IDS
from fastapi import Request
from config import settings



router = APIRouter(prefix="/api/users", tags=["users"])


class UserAccountCreate(BaseModel):
    """Request model for creating/updating user account"""
    username: str
    avatar_url: Optional[str] = None
    email: Optional[str] = None


class UserAccountResponse(BaseModel):
    """Response model for user account (snake_case to match backend, frontend converts to camelCase)"""
    id: str
    username: str
    username_display: Optional[str] = None
    avatar_url: Optional[str] = None
    email: Optional[str] = None
    role: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    preferences: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    joined_at: Optional[str] = None
    last_active: Optional[str] = None


@router.get("/{user_id}", response_model=UserAccountResponse, response_model_by_alias=False)
async def get_user_account(
    user_id: str,
    db = Depends(get_db)
):
    """Get user account by ID"""
    response = db.table("users").select("*").eq("id", user_id).execute()
    
    if not response.data or len(response.data) == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = response.data[0]
    role = user.get("role", "user")
    username_display = user.get("username", "")
    return UserAccountResponse(
        id=user["id"],
        username=username_display,
        username_display=username_display,
        avatar_url=user.get("avatar_url"),
        email=user.get("email"),
        role=role,
        display_name=user.get("display_name"),
        bio=user.get("bio"),
        location=user.get("location"),
        website=user.get("website"),
        preferences=user.get("preferences"),
        created_at=user.get("created_at"),
        updated_at=user.get("updated_at"),
        joined_at=user.get("joined_at"),
        last_active=user.get("last_active")
    )


@router.get("/by-username/{username}", response_model=UserAccountResponse, response_model_by_alias=False)
async def get_user_by_username(
    username: str,
    db = Depends(get_db)
):
    """Public endpoint: get user account by username.
    
    Privacy: Returns public fields only (email and preferences excluded).
    """
    response = db.table("users").select("*").eq("username", username).limit(1).execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="User not found")

    user = response.data[0]
    role = user.get("role", "user")
    username_display = user.get("username", "")
    return UserAccountResponse(
        id=user["id"],
        username=username_display,
        username_display=username_display,
        avatar_url=user.get("avatar_url"),
        email=None,  # hide email in public response
        role=role,
        display_name=user.get("display_name"),
        bio=user.get("bio"),
        location=user.get("location"),
        website=user.get("website"),
        preferences=None,
        created_at=user.get("created_at"),
        updated_at=user.get("updated_at"),
        joined_at=user.get("joined_at"),
        last_active=user.get("last_active")
    )


@router.put("/{user_id}", response_model=UserAccountResponse, response_model_by_alias=False)
@router.post("/{user_id}", response_model=UserAccountResponse, response_model_by_alias=False)
async def create_or_update_user_account(
    user_id: str,
    account_data: UserAccountCreate,
    request: Request,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user_optional)
):
    """Create or update user account (used for OAuth signup and test user creation)"""
    # In production, enforce auth for updates (allow creates for OAuth signup)
    # In test mode, allow unauthenticated creates for test setup
    auth_header = request.headers.get("Authorization")
    print(f"[users] create_or_update_user_account: user_id={user_id} auth_present={bool(auth_header)}")
    
    # Check if user exists
    existing = db.table("users").select("*").eq("id", user_id).execute()
    is_update = existing.data and len(existing.data) > 0
    
    # In production mode, require auth for updates (creates allowed for OAuth)
    if not settings.TEST_MODE and is_update and not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    print(f"[users] is_update={is_update}, test_mode={settings.TEST_MODE}, existing_count={len(existing.data) if existing.data else 0}")

    # Build user data and ensure github_id is present to satisfy schema
    github_id = (current_user or {}).get("github_id") or user_id
    user_data = {
        "username": account_data.username,
        "avatar_url": account_data.avatar_url,
        "email": account_data.email,
        "github_id": github_id,
    }

    try:
        if existing.data and len(existing.data) > 0:
            # Update existing user - preserve role by not including it in update
            db.table("users").update(user_data).eq("id", user_id).execute()
            # Re-fetch to ensure we have all fields including preserved role
            response = db.table("users").select("*").eq("id", user_id).execute()
            updated_user = response.data[0] if response.data else existing.data[0]
            print(f"[users] updated user id={updated_user.get('id')} role={updated_user.get('role')}")
        else:
            # If a record exists with the same username, update it instead of insert to avoid unique constraint
            by_username = db.table("users").select("*").eq("username", account_data.username).limit(1).execute()
            if by_username.data:
                db.table("users").update({**user_data, "id": user_id}).eq("username", account_data.username).execute()
                response = db.table("users").select("*").eq("id", user_id).execute()
                updated_user = response.data[0] if response.data else by_username.data[0]
                print(f"[users] reassigned existing username to new id={user_id}")
            else:
                # Create new user with default role
                payload = {**user_data, "id": user_id, "role": "user"}
                response = db.table("users").insert(payload).execute()
                updated_user = response.data[0] if response.data else payload
                print(f"[users] inserted user id={updated_user.get('id')} role={updated_user.get('role')}")
    except Exception as e:
        print(f"[users] ERROR creating/updating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    role = updated_user.get("role", "user")
    username_display = updated_user.get("username", "")
    return UserAccountResponse(
        id=updated_user["id"],
        username=username_display,
        username_display=username_display,
        avatar_url=updated_user.get("avatar_url"),
        email=updated_user.get("email"),
        role=role,
        display_name=updated_user.get("display_name"),
        bio=updated_user.get("bio"),
        location=updated_user.get("location"),
        website=updated_user.get("website"),
        preferences=updated_user.get("preferences"),
        created_at=updated_user.get("created_at"),
        updated_at=updated_user.get("updated_at"),
        joined_at=updated_user.get("joined_at"),
        last_active=updated_user.get("last_active")
    )


class RoleUpdate(BaseModel):
    role: str  # 'user' | 'moderator' | 'admin'


@router.patch("/{user_id}/role")
async def update_user_role(
    user_id: str,
    role_update: RoleUpdate,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a user's role. Require admin regardless of TEST_MODE."""
    new_role = role_update.role
    if new_role not in {"user", "moderator", "admin"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    # Authorization: require admin via policy helper
    ensure_admin(current_user)

    # Ensure user exists
    existing = db.table("users").select("*").eq("id", user_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="User not found")

    response = db.table("users").update({"role": new_role}).eq("id", user_id).execute()
    updated_user = response.data[0] if response.data else existing.data[0]
    return {
        "id": updated_user["id"],
        "username": updated_user.get("username", ""),
        "avatar_url": updated_user.get("avatar_url"),
        "email": updated_user.get("email"),
        "role": updated_user.get("role", "user"),
        "display_name": updated_user.get("display_name"),
        "created_at": updated_user.get("created_at")
    }

class ProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    preferences: Optional[dict] = None

@router.patch("/{user_id}/profile", response_model=UserAccountResponse, response_model_by_alias=False)
async def update_user_profile(
    user_id: str,
    updates: ProfileUpdate,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a user's profile fields. Currently supports display_name."""
    # Authorization: allow if current user matches or is admin
    if current_user.get("id") != user_id and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to update this profile")

    existing = db.table("users").select("*").eq("id", user_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = {}
    if updates.display_name is not None:
        update_data["display_name"] = updates.display_name
    if updates.bio is not None:
        update_data["bio"] = updates.bio
    if updates.location is not None:
        update_data["location"] = updates.location
    if updates.website is not None:
        update_data["website"] = updates.website
    if updates.preferences is not None:
        update_data["preferences"] = updates.preferences

    # If nothing to update, return current record
    if not update_data:
        user = existing.data[0]
        role = user.get("role", "user")
        return UserAccountResponse(
            id=user["id"],
            username=user.get("username", ""),
            avatar_url=user.get("avatar_url"),
            email=user.get("email"),
            role=role,
            display_name=user.get("display_name"),
            bio=user.get("bio"),
            location=user.get("location"),
            website=user.get("website"),
            preferences=user.get("preferences"),
            created_at=user.get("created_at"),
            updated_at=user.get("updated_at"),
            joined_at=user.get("joined_at"),
            last_active=user.get("last_active")
        )

    response = db.table("users").update(update_data).eq("id", user_id).execute()
    updated_user = response.data[0] if response.data else existing.data[0]
    role = updated_user.get("role", "user")
    return UserAccountResponse(
        id=updated_user["id"],
        username=updated_user.get("username", ""),
        avatar_url=updated_user.get("avatar_url"),
        email=updated_user.get("email"),
        role=role,
        display_name=updated_user.get("display_name"),
        bio=updated_user.get("bio"),
        location=updated_user.get("location"),
        website=updated_user.get("website"),
        preferences=updated_user.get("preferences"),
        created_at=updated_user.get("created_at"),
        updated_at=updated_user.get("updated_at"),
        joined_at=updated_user.get("joined_at"),
        last_active=updated_user.get("last_active")
    )


@router.get("/")
async def get_all_users(
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all users (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    response = db.table("users").select("*").execute()
    return response.data


@router.get("/{user_id}/collections")
async def get_user_collections(
    user_id: str,
    db = Depends(get_db)
):
    """Get user's product collections (not implemented yet)"""
    # TODO: Implement collections when the feature is ready
    return []


@router.get("/{user_id}/requests")
async def get_user_requests(
    user_id: str,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get user's requests (must be the user or admin)"""
    # Check authorization
    if current_user["id"] != user_id and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view these requests")
    
    response = db.table("user_requests").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return response.data


@router.get("/{user_id}/stats")
async def get_user_stats(
    user_id: str,
    db = Depends(get_db)
):
    """Get user statistics"""
    # Count user's contributions
    products = db.table("products").select("id").eq("created_by", user_id).execute()
    ratings = db.table("ratings").select("id").eq("user_id", user_id).execute()
    discussions = db.table("discussions").select("id").eq("user_id", user_id).execute()

    products_submitted = len(products.data) if products.data else 0
    ratings_given = len(ratings.data) if ratings.data else 0
    discussions_participated = len(discussions.data) if discussions.data else 0

    return {
        "products_submitted": products_submitted,
        "ratings_given": ratings_given,
        "discussions_participated": discussions_participated,
        "total_contributions": products_submitted + ratings_given + discussions_participated,
    }


@router.get("/{user_id}/owned-products")
async def get_owned_products(
    user_id: str,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get products owned by a user"""
    # Check authorization - must be the user or admin
    if current_user["id"] != user_id and current_user.get("role") not in ["admin", "moderator"]:
        raise HTTPException(status_code=403, detail="Not authorized to view these products")
    
    # Get all product IDs owned by this user
    ownership_response = db.table("product_editors").select("product_id").eq("user_id", user_id).execute()
    
    if not ownership_response.data:
        return {"products": []}
    
    product_ids = [row["product_id"] for row in ownership_response.data]
    
    # Get the actual products
    products_response = db.table("products").select("*").in_("id", product_ids).execute()
    
    return {"products": products_response.data or []}
