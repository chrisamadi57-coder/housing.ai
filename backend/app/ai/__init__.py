"""AI package.

Every public function here is a pure, testable unit that services and
workers call directly. No DB sessions, no HTTP imports, no Celery.

Each module ships with a rule-based fallback so the platform runs without
any external API keys. Swap implementations individually as models
become available — callers never change.
"""

from app.ai.fraud_detection import FraudAssessment, score_property, score_listing
from app.ai.image_analysis import (
    ImageAnalysisResult,
    analyze_image_bytes,
    analyze_media_row,
)
from app.ai.recommendations import (
    RecommendationResult,
    recommend_for_user,
    similar_listings,
)
from app.ai.search_parser import parse_search_query

__all__ = [
    "parse_search_query",
    "ImageAnalysisResult",
    "analyze_image_bytes",
    "analyze_media_row",
    "FraudAssessment",
    "score_property",
    "score_listing",
    "RecommendationResult",
    "recommend_for_user",
    "similar_listings",
]