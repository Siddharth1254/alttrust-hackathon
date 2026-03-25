from __future__ import annotations
"""
Step 4 - Structure the processed lyrics into a clean JSON schema
suitable for line-by-line display in a vocal-training app.

Output schema per song:
{
  "id": "<artist_slug>__<title_slug>",
  "title": "...",
  "artist": "...",
  "source_language": "korean",
  "target_language": "EN",
  "metadata": { "genius_id": ..., "album": ..., "year": ... },
  "lines": [
    {
      "index": 0,
      "original": "나를 잊어줘",
      "romanized": "nareul ijeo jwo",
      "translation": "Forget me",
      "is_blank": false
    },
    ...
  ],
  "error": null   // or error message string if processing failed
}
"""

import re
import logging
from typing import Optional

from config import PipelineConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Slug helper
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^\w\s-]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = _SLUG_RE.sub("", text)
    text = _WHITESPACE_RE.sub("_", text)
    return text[:60] or "unknown"


# ---------------------------------------------------------------------------
# Structurer class
# ---------------------------------------------------------------------------

class LyricsStructurer:
    def __init__(self, config: PipelineConfig):
        self.config = config

    def structure(
        self,
        title: str,
        artist: str,
        original_lyrics: str,
        romanized_lyrics: Optional[str],
        translated_lyrics: Optional[str],
        source_language: str,
        target_language: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        Build the final structured song object.

        Zips original / romanized / translated lines together so that
        every line object carries all three representations at the same index.
        """
        original_lines  = original_lyrics.splitlines()
        romanized_lines = romanized_lyrics.splitlines() if romanized_lyrics else None
        translated_lines = translated_lyrics.splitlines() if translated_lyrics else None

        # Pad shorter lists with empty strings so zip is safe
        max_len = len(original_lines)
        if romanized_lines is not None:
            romanized_lines = self._pad(romanized_lines, max_len)
        if translated_lines is not None:
            translated_lines = self._pad(translated_lines, max_len)

        lines = []
        for i, orig in enumerate(original_lines):
            line_obj: dict = {
                "index": i,
                "is_blank": not orig.strip(),
            }

            if self.config.include_original_in_lines:
                line_obj["original"] = orig

            if romanized_lines is not None:
                line_obj["romanized"] = romanized_lines[i] if i < len(romanized_lines) else ""
            elif self.config.always_include_romanized:
                line_obj["romanized"] = orig   # for Latin-script songs, same as original

            if translated_lines is not None:
                line_obj["translation"] = translated_lines[i] if i < len(translated_lines) else ""

            lines.append(line_obj)

        return {
            "id": f"{_slugify(artist)}__{_slugify(title)}",
            "title": title,
            "artist": artist,
            "source_language": source_language,
            "target_language": target_language,
            "metadata": metadata or {},
            "lines": lines,
            "error": None,
        }

    def make_error_entry(self, title: str, artist: str, reason: str) -> dict:
        """Return a minimal error placeholder when a song cannot be processed."""
        return {
            "id": f"{_slugify(artist)}__{_slugify(title)}",
            "title": title,
            "artist": artist,
            "source_language": None,
            "target_language": self.config.target_language,
            "metadata": {},
            "lines": [],
            "error": reason,
        }

    @staticmethod
    def _pad(lst: list, length: int) -> list:
        """Extend list with empty strings up to the desired length."""
        return lst + [""] * max(0, length - len(lst))
