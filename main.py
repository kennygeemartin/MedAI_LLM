"""Vercel's FastAPI entry point."""
from importlib import import_module
from importlib.util import find_spec

from fastapi import FastAPI

# Explicit top-level instance for Vercel's static entry-point detection.
app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

# Delete maintenance_patch.py and redeploy to restore the original app,
# including its routes, middleware, and lifespan handlers.
if find_spec("maintenance_patch") is not None:
    app = import_module("maintenance_patch").app
else:
    app = import_module("backend.main").app
