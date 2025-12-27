"""Database access layer providing unified interface to SQLite and Supabase.

Uses database_adapter for automatic backend selection based on settings.
Prefer get_db() over get_supabase() for test/production compatibility.
"""
from supabase import create_client, Client
from config import settings
from database_adapter import DatabaseAdapter

# Initialize database adapter - automatically chooses SQLite (if DATABASE_URL set) or Supabase
db_adapter = DatabaseAdapter(settings)
db_adapter.init()

# Keep Supabase client for backwards compatibility
if settings.SUPABASE_URL:
    supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
else:
    supabase = None


def get_db():
    """
    Dependency for FastAPI endpoints to get database adapter.
    Works with both SQLite (test) and Supabase (production).
    
    Usage:
        @app.get("/example")
        def example(db = Depends(get_db)):
            result = db.table('users').select('*').execute()
            return result.data
    """
    return db_adapter


def get_supabase() -> Client:
    """
    Dependency for FastAPI endpoints to get Supabase client (legacy).
    Use get_db() instead for test/production compatibility.
    """
    if supabase is None:
        raise RuntimeError("Supabase not configured - use get_db() instead")
    return supabase
