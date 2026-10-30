"""Vercel entry point: Vercel runs Python files in api/ as serverless functions and
serves the ASGI `app` they expose. vercel.json routes every path here."""
from app.main import app  # noqa: F401
