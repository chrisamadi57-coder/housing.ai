"""Domain enums shared across the backend and workers."""

from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    USER = "user"
    AGENT = "agent"
    ADMIN = "admin"


class PropertyType(str, enum.Enum):
    APARTMENT = "apartment"
    HOUSE = "house"
    DUPLEX = "duplex"
    BUNGALOW = "bungalow"
    LAND = "land"
    OFFICE = "office"
    SHOP = "shop"
    WAREHOUSE = "warehouse"


class ListingPurpose(str, enum.Enum):
    RENT = "rent"
    SALE = "sale"
    SHORTLET = "shortlet"


class ListingStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    ACTIVE = "active"
    RENTED = "rented"
    SOLD = "sold"
    ARCHIVED = "archived"


class MediaType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    FLOOR_PLAN = "floor_plan"


class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"
    REJECTED = "rejected"