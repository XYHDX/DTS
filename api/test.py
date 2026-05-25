"""Diagnostic endpoint to find the exact crash in index.py."""

from fastapi import FastAPI
import traceback
import sys

app = FastAPI()


@app.get("/api/test")
def test():
    result = {"status": "ok", "python": "working"}

    # Test dependencies
    for mod in ["httpx", "jwt", "bcrypt", "pydantic", "dotenv"]:
        try:
            __import__(mod)
            result[mod] = "ok"
        except Exception as e:
            result[mod] = str(e)

    import os

    result["SUPABASE_URL"] = "set" if os.getenv("SUPABASE_URL") else "missing"
    result["SUPABASE_KEY"] = "set" if os.getenv("SUPABASE_KEY") else "missing"
    result["SUPABASE_SERVICE_KEY"] = (
        "set" if os.getenv("SUPABASE_SERVICE_KEY") else "missing"
    )
    result["JWT_SECRET"] = "set" if os.getenv("JWT_SECRET") else "missing"

    # Try importing the main module
    try:
        # Add parent to path

        sys.path.insert(0, os.path.dirname(__file__))
        import index

        result["index_import"] = "ok"
        result["has_app"] = hasattr(index, "app")
    except Exception as e:
        result["index_import"] = "FAILED"
        result["index_error"] = str(e)
        result["index_traceback"] = traceback.format_exc()[-500:]

    return result
