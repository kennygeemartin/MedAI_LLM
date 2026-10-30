"""Vercel's FastAPI entry point."""
from importlib.util import find_spec

# Delete maintenance_patch.py and redeploy to restore the normal application.
if find_spec("maintenance_patch") is not None:
    from maintenance_patch import app
else:
    from backend.main import app
