"""
Supabase database client initialization and utility functions.
Handles connection pooling and provides helper methods for common queries.
"""

import os
from typing import Optional, Any, Dict
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


class SupabaseDB:
    """Singleton Supabase client wrapper with connection pooling."""

    _instance: Optional["SupabaseDB"] = None
    _client: Optional[Client] = None

    def __new__(cls) -> "SupabaseDB":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            if not SUPABASE_URL or not SUPABASE_KEY:
                raise ValueError(
                    "SUPABASE_URL and SUPABASE_KEY environment variables are required"
                )
            self._client = create_client(SUPABASE_URL, SUPABASE_KEY)

    @property
    def client(self) -> Client:
        """Get the Supabase client instance."""
        return self._client

    def table(self, name: str):
        """Get a table reference."""
        return self._client.table(name)

    def rpc(self, func_name: str, params: Dict[str, Any]):
        """Call a remote procedure (PostgreSQL function)."""
        return self._client.rpc(func_name, params)

    def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            self._client.table("users").select("id").limit(1).execute()
            return True
        except Exception as e:
            print(f"Database health check failed: {e}")
            return False


# Global singleton instance
_db = SupabaseDB()


def get_db() -> SupabaseDB:
    """Get the global Supabase database instance."""
    return _db


def get_supabase_client() -> Client:
    """Get the raw Supabase client for direct access."""
    return _db.client
