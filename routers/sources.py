"""Admin API endpoints for managing supported product sources."""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from models.sources import SupportedSourceCreate, SupportedSourceResponse, SupportedSourceUpdate
from services.database import get_db
from services.auth import get_current_user
from services.id_generator import generate_id_with_uniqueness_check

router = APIRouter(prefix="/api/supported-sources", tags=["supported-sources"])


@router.get("", response_model=list[SupportedSourceResponse])
async def get_supported_sources(
    db = Depends(get_db),
):
    """Get all supported product sources (public endpoint)."""
    response = db.table("supported_sources").select("*").order("created_at").execute()
    return response.data or []


@router.post("", response_model=SupportedSourceResponse, status_code=201)
async def create_supported_source(
    source: SupportedSourceCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Create a new supported source (admin only).
    
    Security: Requires admin role.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if domain already exists
    existing = db.table("supported_sources").select("*").eq("domain", source.domain.lower()).limit(1).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="This domain is already supported")
    
    # Generate ID and create record
    source_id = generate_id_with_uniqueness_check(db, "supported_sources")
    
    db_data = {
        "id": source_id,
        "domain": source.domain.lower(),
        "name": source.name,
    }
    
    response = db.table("supported_sources").insert(db_data).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create supported source")
    
    return response.data[0]


@router.put("/{source_id}", response_model=SupportedSourceResponse)
async def update_supported_source(
    source_id: str,
    source: SupportedSourceUpdate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Update a supported source (admin only).
    
    Security: Requires admin role.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if source exists
    existing = db.table("supported_sources").select("*").eq("id", source_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Build update data (only non-None fields)
    update_data = {}
    if source.domain is not None:
        # Check if new domain already exists elsewhere
        domain_check = db.table("supported_sources").select("*").eq("domain", source.domain.lower()).limit(1).execute()
        if domain_check.data and domain_check.data[0]["id"] != source_id:
            raise HTTPException(status_code=409, detail="This domain is already supported")
        update_data["domain"] = source.domain.lower()
    
    if source.name is not None:
        update_data["name"] = source.name
    
    if not update_data:
        # No changes, return existing
        return existing.data[0]
    
    response = db.table("supported_sources").update(update_data).eq("id", source_id).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to update supported source")
    
    return response.data[0]


@router.delete("/{source_id}", status_code=204)
async def delete_supported_source(
    source_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Delete a supported source (admin only).
    
    Security: Requires admin role.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if source exists
    existing = db.table("supported_sources").select("*").eq("id", source_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Delete the source
    db.table("supported_sources").delete().eq("id", source_id).execute()
    return None
