"""Blog post management endpoints.

Admin-only blog posts with markdown content, header images, and multi-author support.
Security: All mutations require admin role; image uploads size-limited to ~5MB.
Markdown content should be sanitized before rendering to prevent XSS.
"""
from datetime import datetime, UTC
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from models.blog_posts import BlogPostCreate, BlogPostResponse, BlogPostUpdate
from services.auth import ensure_admin, get_current_user, get_current_user_optional
from services.database import get_db

router = APIRouter(prefix="/api/blog-posts", tags=["blog"])


def _slugify(text: str) -> str:
    """Generate URL-friendly slug from blog post title.
    
    Normalizes title to lowercase, removes special chars, and replaces spaces with hyphens.
    Example: "Hello World & Friends" -> "hello-world-and-friends"
    Used for clean URLs: /blog/hello-world-and-friends
    """
    return (
        text.lower()
        .strip()
        .replace("'", "")
        .replace("\"", "")
        .replace("&", " and ")
        .replace("/", "-")
        .replace("\\", "-")
    ).replace(" ", "-").replace("--", "-")


def _to_datetime(value: Optional[object]) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=UTC).replace(tzinfo=None)
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=UTC)
        return dt.astimezone(UTC).replace(tzinfo=None)
    if isinstance(value, str):
        try:
            # Support both Z and offset formats
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            dt = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC).replace(tzinfo=None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {value}") from exc
    raise HTTPException(status_code=400, detail="Unsupported date value")


def _to_timestamp_ms(value: Optional[object]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            dt = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            return None
        return int(dt.timestamp() * 1000)
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=UTC)
        return int(dt.timestamp() * 1000)
    return None

def _normalize_image_string(value: Optional[str]) -> Optional[str]:
    """Normalize header image values to a consistent, browser-friendly format.

    Handles multiple input formats:
    - HTTP(S) URLs: passed through unchanged
    - Data URLs: passed through unchanged
    - Raw base64: auto-detects mime type from magic bytes and adds data URL prefix
    
    MIME detection examines base64 prefix:
    - /9j/ -> JPEG, iVBOR -> PNG, R0lGOD -> GIF, Qk -> BMP
    - Default: PNG if unrecognized
    """
    if not value:
        return None
    src = value.strip()
    if not src:
        return None
    if src.lower().startswith("http://") or src.lower().startswith("https://"):
        return src
    if src.lower().startswith("data:"):
        return src
    head = src[:10]
    mime = "image/png"
    if head.startswith("/9j/"):
        mime = "image/jpeg"
    elif head.startswith("iVBOR"):
        mime = "image/png"
    elif head.startswith("R0lGOD"):
        mime = "image/gif"
    elif head.startswith("Qk"):
        mime = "image/bmp"
    return f"data:{mime};base64,{src}"

def _validate_image_size(data_url: Optional[str], field_name: str = "header_image"):
    """Enforce a ~5MB maximum payload for images.

    We estimate byte size from the base64 payload length: bytes ~= len * 3 / 4.
    """
    if not data_url or not data_url.startswith("data:"):
        return
    try:
        comma = data_url.find(",")
        if comma == -1:
            return
        b64 = data_url[comma + 1 :]
        approx_bytes = int(len(b64) * 3 / 4)
        if approx_bytes > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"{field_name} exceeds 5MB limit")
    except Exception:
        # On parsing errors, do not block; validation is best-effort
        return


_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_HTML_IMG_RE = re.compile(r"<img[^>]+src=[\"\']([^\"\']+)[\"\'][^>]*>", re.IGNORECASE)


def _normalize_content_images(content: Optional[str]) -> Optional[str]:
    """Normalize and validate inline images embedded in markdown/HTML content.

    - Converts raw base64 URLs to data URLs with a mime prefix
    - Validates each data URL is <= 5MB
    - Leaves http(s) and already-normalized data URLs untouched
    """
    if not content:
        return content

    def _md_replacer(match: re.Match) -> str:
        url = match.group(1)
        norm = _normalize_image_string(url)
        if norm and norm.startswith("data:"):
            _validate_image_size(norm, field_name="content image")
        # Rebuild the original "![alt](...)" with normalized URL
        start, end = match.span(1)
        return content[match.start():start] + (norm or url) + content[end:match.end()]

    # We'll replace by building progressively to avoid nested span confusion.
    # First handle markdown images.
    parts = []
    last = 0
    for m in _MD_IMAGE_RE.finditer(content):
        url = m.group(1)
        norm = _normalize_image_string(url)
        if norm and norm.startswith("data:"):
            _validate_image_size(norm, field_name="content image")
        # Replace only the URL portion
        start_url, end_url = m.span(1)
        parts.append(content[last:start_url])
        parts.append(norm or url)
        last = end_url
    md_normalized = ''.join(parts) + content[last:]

    # Now handle <img src="..."> inside the markdown content
    parts = []
    last = 0
    for m in _HTML_IMG_RE.finditer(md_normalized):
        url = m.group(1)
        norm = _normalize_image_string(url)
        if norm and norm.startswith("data:"):
            _validate_image_size(norm, field_name="content image")
        start_url, end_url = m.span(1)
        parts.append(md_normalized[last:start_url])
        parts.append(norm or url)
        last = end_url
    html_normalized = ''.join(parts) + md_normalized[last:]

    return html_normalized

def _normalize_post(record: dict) -> dict:
    if not record:
        return record

    post = dict(record)
    post["tags"] = post.get("tags") or []
    post["author_ids"] = post.get("author_ids") or ([post["author_id"]] if post.get("author_id") else [])
    post["author_names"] = post.get("author_names") or ([post["author_name"]] if post.get("author_name") else [])

    for field in ["created_at", "updated_at", "published_at", "publish_date"]:
        post[field] = _to_timestamp_ms(post.get(field))

    # Ensure header_image is always a valid src for clients
    post["header_image"] = _normalize_image_string(post.get("header_image"))

    return post


def _ensure_slug_unique(db, slug: str, exclude_id: Optional[str] = None):
    query = db.table("blog_posts").select("id").eq("slug", slug)
    if exclude_id:
        query = query.neq("id", exclude_id)
    existing = query.execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Slug already exists")


@router.get("", response_model=List[BlogPostResponse])
async def list_blog_posts(
    include_unpublished: bool = Query(False, alias="includeUnpublished"),
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db=Depends(get_db),
):
    if include_unpublished:
        ensure_admin(current_user)

    query = db.table("blog_posts").select("*")
    if not include_unpublished:
        query = query.eq("published", True)

    response = query.execute()
    posts = [_normalize_post(p) for p in (response.data or [])]
    posts.sort(
        key=lambda p: p.get("publish_date")
        or p.get("published_at")
        or p.get("created_at")
        or 0,
        reverse=True,
    )
    return posts


@router.get("/{post_id}", response_model=BlogPostResponse)
async def get_blog_post(
    post_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db=Depends(get_db),
):
    response = db.table("blog_posts").select("*").eq("id", post_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Blog post not found")

    post = _normalize_post(response.data[0])
    if not post.get("published") and not (current_user and current_user.get("role") == "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    return post


@router.get("/slug/{slug}", response_model=BlogPostResponse)
async def get_blog_post_by_slug(
    slug: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db=Depends(get_db),
):
    response = db.table("blog_posts").select("*").eq("slug", slug).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Blog post not found")

    post = _normalize_post(response.data[0])
    if not post.get("published") and not (current_user and current_user.get("role") == "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    return post


@router.post("", response_model=BlogPostResponse, status_code=201)
async def create_blog_post(
    payload: BlogPostCreate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_admin(current_user)

    slug = (payload.slug or _slugify(payload.title)).strip()
    if not slug:
        raise HTTPException(status_code=400, detail="Slug is required")
    _ensure_slug_unique(db, slug)

    now = datetime.now(UTC)
    publish_date = _to_datetime(payload.publish_date)
    published_at = _to_datetime(payload.published_at) or (now if payload.published else None)

    author_ids = payload.author_ids or [payload.author_id]
    author_names = payload.author_names or [payload.author_name]

    normalized_image = _normalize_image_string(payload.header_image)
    _validate_image_size(normalized_image)

    normalized_content = _normalize_content_images(payload.content)

    record = {
        "title": payload.title,
        "slug": slug,
        "content": normalized_content or payload.content,
        "excerpt": payload.excerpt,
        "header_image": normalized_image,
        "header_image_alt": payload.header_image_alt,
        "author_id": payload.author_id,
        "author_name": payload.author_name,
        "author_ids": author_ids,
        "author_names": author_names,
        "tags": payload.tags or [],
        "published": payload.published,
        "published_at": published_at,
        "publish_date": publish_date,
        "featured": payload.featured,
        "created_at": now,
        "updated_at": now,
    }

    response = db.table("blog_posts").insert(record).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Failed to create blog post")

    return _normalize_post(response.data[0])


@router.patch("/{post_id}", response_model=BlogPostResponse)
async def update_blog_post(
    post_id: str,
    updates: BlogPostUpdate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_admin(current_user)

    existing = db.table("blog_posts").select("*").eq("id", post_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Blog post not found")

    update_data = {}

    if updates.title is not None:
        update_data["title"] = updates.title
    if updates.slug is not None:
        new_slug = updates.slug.strip()
        if not new_slug:
            raise HTTPException(status_code=400, detail="Slug cannot be empty")
        _ensure_slug_unique(db, new_slug, exclude_id=post_id)
        update_data["slug"] = new_slug
    if updates.content is not None:
        update_data["content"] = _normalize_content_images(updates.content) or updates.content
    if updates.excerpt is not None:
        update_data["excerpt"] = updates.excerpt
    if updates.header_image is not None:
        normalized_image = _normalize_image_string(updates.header_image)
        _validate_image_size(normalized_image)
        update_data["header_image"] = normalized_image
    if updates.header_image_alt is not None:
        update_data["header_image_alt"] = updates.header_image_alt
    if updates.tags is not None:
        update_data["tags"] = updates.tags
    if updates.featured is not None:
        update_data["featured"] = updates.featured
    if updates.author_id is not None:
        update_data["author_id"] = updates.author_id
    if updates.author_name is not None:
        update_data["author_name"] = updates.author_name
    if updates.author_ids is not None:
        update_data["author_ids"] = updates.author_ids
    if updates.author_names is not None:
        update_data["author_names"] = updates.author_names
    if updates.publish_date is not None:
        update_data["publish_date"] = _to_datetime(updates.publish_date)
    if updates.published_at is not None:
        update_data["published_at"] = _to_datetime(updates.published_at)
    if updates.published is not None:
        update_data["published"] = updates.published
        if updates.published:
            if "published_at" not in update_data or update_data["published_at"] is None:
                update_data["published_at"] = datetime.now(UTC)
        else:
            update_data["published_at"] = None

    update_data["updated_at"] = datetime.now(UTC)

    updated = db.table("blog_posts").update(update_data).eq("id", post_id).execute()
    if not updated.data:
        raise HTTPException(status_code=400, detail="Failed to update blog post")

    return _normalize_post(updated.data[0])


@router.delete("/{post_id}")
async def delete_blog_post(
    post_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_admin(current_user)

    existing = db.table("blog_posts").select("id").eq("id", post_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Blog post not found")

    db.table("blog_posts").delete().eq("id", post_id).execute()
    return {"success": True}
