"""Centralized runtime configuration helpers for Research Nexus."""
import os


def is_production() -> bool:
    return os.getenv("NODE_ENV", "").strip().lower() == "production"


def get_google_api_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()


def get_openrouter_api_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "").strip()


def get_ai_provider() -> str:
    return os.getenv("AI_PROVIDER", "openrouter").strip().lower() or "openrouter"


def is_mock_ai_enabled() -> bool:
    mock_env = os.getenv("MOCK_AI", "").strip().lower()
    return mock_env in ("true", "1", "yes")


def max_ai_requests_per_minute() -> int:
    try:
        return int(os.getenv("AI_MAX_REQUESTS_PER_MINUTE", "60"))
    except Exception:
        return 60
