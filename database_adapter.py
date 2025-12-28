"""
Database adapter that works with both Supabase and SQLite

This allows tests to use SQLite (fast, local) while production uses Supabase.
The adapter provides a unified interface that works with both backends.
"""
from typing import Optional, Dict, List, Any, Union
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Text, JSON, Float, UUID
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime, UTC
import uuid
from services.id_generator import normalize_to_snake_case

Base = declarative_base()


def utcnow_naive():
    """
    Return current UTC time as a naive datetime (tzinfo=None).
    Avoids deprecated datetime.utcnow() while keeping existing schema semantics.
    """
    return datetime.now(UTC).replace(tzinfo=None)


# SQLAlchemy models for SQLite
class Product(Base):
    __tablename__ = "products"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=True, unique=True)  # Allow NULL for user-submitted products without links
    description = Column(Text)
    type = Column(String)  # Product type (e.g., Software, Knitting, 3D Print)
    source = Column(String)
    image = Column(String)  # Product image URL
    external_id = Column(String)  # External platform ID
    external_data = Column(JSON)  # Additional data from source
    source_rating = Column(Float)  # Average rating from source platform
    source_rating_count = Column(Integer)  # Number of ratings from source platform
    source_last_updated = Column(DateTime)  # Last updated timestamp from source platform
    scraped_at = Column(DateTime)  # Last scraped timestamp
    banned = Column(Boolean, default=False)
    banned_reason = Column(Text)
    banned_by = Column(String)
    banned_at = Column(DateTime)
    created_by = Column(String)  # User who created/added the product
    editor_ids = Column(JSON)  # List of editor user IDs
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    last_edited_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    last_edited_by = Column(String)
    image_alt = Column(String)


class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    github_id = Column(String, unique=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String)
    display_name = Column(String)
    role = Column(String, default="user")  # 'admin', 'moderator', 'user'
    avatar_url = Column(String)
    created_at = Column(DateTime, default=utcnow_naive)
    bio = Column(String)
    location = Column(String)
    website = Column(String)
    joined_at = Column(DateTime, default=utcnow_naive)
    last_active = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive)


class Rating(Base):
    __tablename__ = "ratings"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(UUID(as_uuid=False), nullable=False)
    user_id = Column(String, nullable=False)
    rating = Column(Integer, nullable=False)
    owned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)


class Discussion(Base):
    __tablename__ = "discussions"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(UUID(as_uuid=False), nullable=False)
    user_id = Column(String, nullable=False)
    username = Column(String)  # Denormalized username for display
    content = Column(Text, nullable=False)
    parent_id = Column(UUID(as_uuid=False))  # For threaded discussions
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    # Moderation fields
    blocked = Column(Boolean, default=False)
    blocked_by = Column(String)
    blocked_reason = Column(Text)
    blocked_at = Column(DateTime)


class ScrapingLog(Base):
    __tablename__ = "scraping_logs"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String)
    source = Column(String, nullable=False)
    products_found = Column(Integer, default=0)
    products_added = Column(Integer, default=0)
    products_updated = Column(Integer, default=0)
    duration_seconds = Column(Float)
    status = Column(String)
    error_message = Column(Text)
    created_at = Column(DateTime, default=utcnow_naive)


class OAuthConfig(Base):
    __tablename__ = "oauth_configs"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    platform = Column(String, unique=True, nullable=False)
    client_id = Column(String)
    client_secret = Column(String)
    redirect_uri = Column(String)
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime)
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive)


class UserRequest(Base):
    __tablename__ = "user_requests"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    type = Column(String, nullable=False)  # 'moderator', 'admin', 'product-ownership'
    status = Column(String, default='pending')  # 'pending', 'approved', 'rejected'
    product_id = Column(UUID(as_uuid=False))  # For product-ownership requests
    reason = Column(Text)  # User's reason for the request
    reviewed_by = Column(String)  # Admin who reviewed the request
    reviewed_at = Column(DateTime)
    reviewer_note = Column(String)
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive)


class ProductOwner(Base):
    __tablename__ = "product_editors"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(UUID(as_uuid=False), nullable=False)
    user_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow_naive)


class ProductUrl(Base):
    __tablename__ = "product_urls"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(UUID(as_uuid=False), nullable=False)
    url = Column(String, nullable=False)
    description = Column(Text)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)


class Tag(Base):
    __tablename__ = "tags"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=utcnow_naive)


class ProductTag(Base):
    __tablename__ = "product_tags"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(UUID(as_uuid=False), nullable=False)
    tag_id = Column(UUID(as_uuid=False), nullable=False)
    created_at = Column(DateTime, default=utcnow_naive)


class UserActivity(Base):
    __tablename__ = "user_activities"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    type = Column(String, nullable=False)  # 'product_submit', 'rating', 'discussion', 'tag'
    product_id = Column(UUID(as_uuid=False))
    timestamp = Column(Integer, nullable=False)  # milliseconds since epoch
    activity_metadata = Column(JSON)  # Renamed from 'metadata' which is reserved by SQLAlchemy
    created_at = Column(DateTime, default=utcnow_naive)


class Collection(Base):
    __tablename__ = "collections"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    user_name = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    product_ids = Column(JSON, default=list)  # List of product UUIDs
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)


class BlogPost(Base):
    __tablename__ = "blog_posts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(Text, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    content = Column(Text, nullable=False)
    excerpt = Column(Text)
    header_image = Column(Text)
    header_image_alt = Column(Text)
    author_id = Column(String, nullable=False)
    author_name = Column(String, nullable=False)
    author_ids = Column(JSON)
    author_names = Column(JSON)
    published = Column(Boolean, default=False)
    published_at = Column(DateTime)
    publish_date = Column(DateTime)
    tags = Column(JSON)
    featured = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)


class SupportedSource(Base):
    __tablename__ = "supported_sources"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    domain = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)


class ScraperSearchTerms(Base):
    __tablename__ = "scraper_search_terms"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    platform = Column(String, unique=True, nullable=False)
    search_terms = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)


class DatabaseAdapter:
    """
    Database adapter that works with both Supabase and SQLite
    
    Usage:
        # Automatically uses SQLite if DATABASE_URL is set (tests)
        # Otherwise uses Supabase (production)
        
        db = DatabaseAdapter(settings)
        await db.init()
        
        # Same API for both backends
        result = db.table("products").select("*").eq("id", "123").execute()
    """
    
    def __init__(self, settings=None):
        from config import get_settings
        self.settings = settings or get_settings()
        self.engine = None
        self.Session = None
        self.supabase = None
        self._initialized = False
        
        # Determine which backend to use
        if self.settings.DATABASE_URL:
            # Use SQLite (tests)
            self.backend = "sqlite"
            # Remove aiosqlite:// prefix for synchronous engine
            db_url = self.settings.DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://")
            self.engine = create_engine(db_url, echo=False)
            self.Session = sessionmaker(bind=self.engine)
        elif self.settings.SUPABASE_URL:
            # Use Supabase (production)
            self.backend = "supabase"
            from supabase import create_client
            self.supabase = create_client(
                self.settings.SUPABASE_URL,
                self.settings.SUPABASE_KEY
            )
        else:
            raise ValueError("Must provide either DATABASE_URL or SUPABASE_URL")
    
    def init(self):
        """Initialize database (create tables for SQLite)"""
        if self.backend == "sqlite" and not self._initialized:
            Base.metadata.create_all(self.engine)
            self._initialized = True
    
    def cleanup(self):
        """Clean up database (for testing)"""
        if self.backend == "sqlite":
            Base.metadata.drop_all(self.engine)
            Base.metadata.create_all(self.engine)
    
    def table(self, table_name: str):
        """Get table interface (compatible with Supabase API)"""
        if self.backend == "sqlite":
            return SQLiteTable(table_name, self.Session)
        else:
            return self.supabase.table(table_name)


class SQLiteTable:
    """
    SQLite table interface that mimics Supabase table API
    
    Provides a similar interface to Supabase for compatibility.
    """
    
    # Map table names to SQLAlchemy models
    MODELS = {
        "products": Product,
        "users": User,
        "ratings": Rating,
        "discussions": Discussion,
        "scraping_logs": ScrapingLog,
        "oauth_configs": OAuthConfig,
        "user_requests": UserRequest,
        "product_editors": ProductOwner,
        "product_urls": ProductUrl,
        "user_activities": UserActivity,
        "tags": Tag,
        "product_tags": ProductTag,
        "collections": Collection,
        "blog_posts": BlogPost,
        "supported_sources": SupportedSource,
        "scraper_search_terms": ScraperSearchTerms,
    }
    
    def __init__(self, table_name: str, Session):
        self.table_name = table_name
        self.Session = Session
        self.model = self.MODELS.get(table_name)
        self._select_cols = "*"
        self._filters = []
        self._insert_data = None
        self._update_data = None
        self._upsert_data = None
        self._delete = False
        self._limit_val = None
        self._offset_val = None
        self._order_col = None
        self._order_desc = False
        
        if not self.model:
            raise ValueError(f"Unknown table: {table_name}")
    
    def select(self, columns: str = "*"):
        """Select columns"""
        self._select_cols = columns
        return self
    
    def insert(self, data: Union[Dict, List[Dict]]):
        """Insert data"""
        self._insert_data = data if isinstance(data, list) else [data]
        return self
    
    def update(self, data: Dict):
        """Update data"""
        self._update_data = data
        return self

    def upsert(self, data: Dict):
        """Upsert data by 'platform' unique key if present (Supabase-compatible)."""
        self._upsert_data = data
        return self
    
    def eq(self, column: str, value: Any):
        """Filter by equality"""
        self._filters.append((column, "==", value))
        return self
    
    def neq(self, column: str, value: Any):
        """Filter by inequality"""
        self._filters.append((column, "!=", value))
        return self
    
    def gt(self, column: str, value: Any):
        """Filter by greater than"""
        self._filters.append((column, ">", value))
        return self
    
    def lt(self, column: str, value: Any):
        """Filter by less than"""
        self._filters.append((column, "<", value))
        return self
    
    def limit(self, count: int):
        """Limit results"""
        self._limit_val = count
        return self
    
    def range(self, start: int, end: int):
        """Range-based pagination (Supabase compatible)"""
        self._offset_val = start
        self._limit_val = end - start + 1
        return self

    def ilike(self, column: str, pattern: Any):
        """Case-insensitive pattern match (SQLite fallback)"""
        self._filters.append((column, "ilike", pattern))
        return self

    def in_(self, column: str, values: List[Any]):
        """Filter by inclusion set"""
        self._filters.append((column, "in", values))
        return self
    
    def order(self, column: str, desc: bool = False):
        """Order results"""
        self._order_col = column
        self._order_desc = desc
        return self
    
    def delete(self):
        """Delete matching records"""
        self._delete = True
        return self
    
    def execute(self):
        """Execute the query"""
        session = self.Session()
        
        try:
            # Handle INSERT
            if self._insert_data:
                objects = []
                for item in self._insert_data:
                    prepared = self._prepare_data(item)

                    # Ensure products always have a slug even if callers omit it (legacy tests/fixtures)
                    if self.table_name == "products":
                        prepared = self._ensure_product_slug(prepared, session)

                    obj = self.model(**prepared)
                    session.add(obj)
                    objects.append(obj)
                session.commit()
                
                # Refresh to get generated values
                for obj in objects:
                    session.refresh(obj)
                
                # Convert to dict
                data = [self._model_to_dict(obj) for obj in objects]
                return type('Result', (), {'data': data, 'count': len(data)})()
            
            # Handle UPDATE
            elif self._update_data:
                query = session.query(self.model)
                query = self._apply_filters(query)
                
                # Get objects before update so we can return them
                objects = query.all()
                
                # Update the objects
                prepared_update = self._prepare_data(self._update_data)
                for obj in objects:
                    for key, value in prepared_update.items():
                        setattr(obj, key, value)
                
                session.commit()
                
                # Refresh to get updated values
                for obj in objects:
                    session.refresh(obj)
                
                # Convert to dict
                data = [self._model_to_dict(obj) for obj in objects]
                return type('Result', (), {'data': data, 'count': len(data)})()

            # Handle UPSERT (by 'platform' when available)
            elif self._upsert_data:
                prepared_upsert = self._prepare_data(self._upsert_data)
                # If table has 'platform' column and provided, perform update-or-insert
                platform_value = prepared_upsert.get("platform")
                if platform_value is not None and hasattr(self.model, "platform"):
                    obj = session.query(self.model).filter(getattr(self.model, "platform") == platform_value).first()
                    if obj is None:
                        obj = self.model(**prepared_upsert)
                        session.add(obj)
                    else:
                        for key, value in prepared_upsert.items():
                            setattr(obj, key, value)
                    session.commit()
                    session.refresh(obj)
                    data = [self._model_to_dict(obj)]
                    return type('Result', (), {'data': data, 'count': 1})()
                else:
                    # Fallback: insert
                    obj = self.model(**prepared_upsert)
                    session.add(obj)
                    session.commit()
                    session.refresh(obj)
                    data = [self._model_to_dict(obj)]
                    return type('Result', (), {'data': data, 'count': 1})()
            
            # Handle DELETE
            elif self._delete:
                query = session.query(self.model)
                query = self._apply_filters(query)
                count = query.delete()
                session.commit()
                return type('Result', (), {'data': [], 'count': count})()
            
            # Handle SELECT
            else:
                query = session.query(self.model)
                query = self._apply_filters(query)
                
                if self._order_col:
                    col = getattr(self.model, self._order_col)
                    query = query.order_by(col.desc() if self._order_desc else col)
                
                if self._offset_val is not None:
                    query = query.offset(self._offset_val)
                
                if self._limit_val:
                    query = query.limit(self._limit_val)
                
                results = query.all()
                data = [self._model_to_dict(obj) for obj in results]
                return type('Result', (), {'data': data, 'count': len(data)})()
        
        finally:
            session.close()

    def _ensure_product_slug(self, item: Dict[str, Any], session: Session) -> Dict[str, Any]:
        """Populate a slug for products when missing to satisfy NOT NULL/UNIQUE constraints."""
        if item.get("slug"):
            return item

        # Prefer name, fall back to URL, then a generic prefix
        base_source = item.get("name") or item.get("url") or "product"
        base_slug = normalize_to_snake_case(base_source) or "product"

        slug = base_slug
        counter = 1
        # Guarantee uniqueness at insert time
        while session.query(Product).filter(Product.slug == slug).first() is not None:
            slug = f"{base_slug}-{counter}"
            counter += 1

        item = {**item, "slug": slug}
        return item
    
    def _apply_filters(self, query):
        """Apply filters to query"""
        for column, op, value in self._filters:
            col = getattr(self.model, column)
            if op == "==":
                query = query.filter(col == value)
            elif op == "!=":
                query = query.filter(col != value)
            elif op == ">":
                query = query.filter(col > value)
            elif op == "<":
                query = query.filter(col < value)
            elif op == "ilike":
                query = query.filter(col.ilike(value))
            elif op == "in":
                query = query.filter(col.in_(value))
        return query
    
    def _model_to_dict(self, obj):
        """Convert SQLAlchemy model to dict"""
        result = {}
        for column in obj.__table__.columns:
            value = getattr(obj, column.name)
            # Convert datetime to ISO string
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result

    def _prepare_data(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Filter and map incoming data to model columns.

        Handles newer field names used by scrapers so inserts don't fail when
        the SQLite schema lacks those columns (e.g., source_url/image_url/type).
        """
        if not isinstance(item, dict):
            return item

        prepared: Dict[str, Any] = {}
        model_columns = {col.name for col in self.model.__table__.columns}

        # Map newer fields to legacy columns where appropriate
        if "source_url" in item and "url" in model_columns and "url" not in item:
            item = {**item, "url": item["source_url"]}
        if "image_url" in item and "image" in model_columns and "image" not in item:
            item = {**item, "image": item["image_url"]}
        # If a generic type field exists, map to category when type column missing
        if "type" in item and "type" not in model_columns and "category" in model_columns and "category" not in item:
            item = {**item, "category": item["type"]}

        # Only keep keys that exist on the model
        for key, value in item.items():
            if key in model_columns:
                prepared[key] = value

        return prepared
