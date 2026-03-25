"""
Pipeline configuration — all tuneable settings in one place.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class PipelineConfig:
    # --- API credentials ---
    # We prioritize GENIUS_TOKEN, but also support CLIENT_ID/CLIENT_secret
    genius_token: str = os.getenv("GENIUS_TOKEN")
    genius_client_id: str = os.getenv("CLIENT_ID") or os.getenv("GENIUS_ID")
    genius_client_secret: str = os.getenv("CLIENT_SECRET") or os.getenv("CLIENT_secret")
    deepl_api_key: str = os.getenv("DEEPL_API_KEY")
    openai_api_key: str = os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_KEY")
    # "deepl" | "openai"
    translation_backend: str = os.getenv("TRANSLATION_BACKEND", "openai") if (os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_KEY")) else os.getenv("TRANSLATION_BACKEND", "deepl")

    def __post_init__(self):
        """Clean up credentials (strip quotes/whitespace)."""
        for attr in ["genius_token", "genius_client_id", "genius_client_secret", "deepl_api_key", "openai_api_key"]:
            val = getattr(self, attr)
            if isinstance(val, str):
                setattr(self, attr, val.strip().strip('"'))

    # --- Language settings ---
    # DeepL target language code (e.g. "EN", "FR", "DE", "ES")
    target_language: str = "EN"

    # --- Romanization ---
    # "kakasi"   -> pykakasi (Japanese)
    # "romanize" -> romanize (Korean via romanize-hangul)
    # "auto"     -> detect script, pick the right library
    romanization_backend: str = "auto"

    # --- Fetch settings ---
    # Max retries on transient network errors
    fetch_max_retries: int = 3
    # Seconds to wait between songs (rate-limit courtesy)
    request_delay_seconds: float = 1.0
    # Remove [Verse], [Chorus] section headers from lyrics
    strip_section_headers: bool = True
    # Remove lines that are purely English within a non-English song
    strip_english_fillers: bool = False

    # --- Output settings ---
    # Include romanized field even when source is already Latin-script
    always_include_romanized: bool = False
    # Include raw original field in every line object
    include_original_in_lines: bool = True

    # --- Language detection ---
    # Minimum fraction of CJK/Hangul chars to classify a line as non-Latin
    cjk_threshold: float = 0.15

    # --- DeepL settings ---
    # Formality preference (passed to DeepL when supported)
    # Options: "default" | "more" | "less" | "prefer_more" | "prefer_less"
    deepl_formality: str = "default"
    # Max characters per DeepL request (free tier: 500k/month)
    deepl_chunk_size: int = 4000
