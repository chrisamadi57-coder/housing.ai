"""Routes package.

Each module exposes a single ``router``. Import them here so ``main.py``
can register them in one loop.
"""

from app.routes import auth, listings, media, properties, search, verification

__all__ = ["auth", "properties", "listings", "media", "search", "verification"]