"""Compatibility shim retained for older imports.

Research Nexus no longer initializes or calls Vertex AI. New code should import
``google_ai.analyze_with_google_ai`` instead.
"""

from google_ai import analyze_with_google_ai


def analyze_with_vertex(text: str):
    """Deprecated alias that delegates to the configured Google API provider."""
    return analyze_with_google_ai(text)
