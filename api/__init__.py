"""Damascus Transit FastAPI backend — root package marker.

Without this file, `from api.core.logging import ...` (the very first
import in api/index.py) fails with ImportError, crashing the Vercel
serverless function before any env vars can even be read. The other
three subdirectories (api/core/, api/routers/, api/models/) already
have their own __init__.py files; this completes the package hierarchy.
"""
