from __future__ import annotations
"""
Step 2 - Romanize Korean (Hangul) or Japanese (Kanji/Kana) lyrics.

Libraries used:
  - korean-romanizer  (pip install korean-romanizer)
      Converts Hangul syllables to Revised Romanization of Korean.
  - pykakasi           (pip install pykakasi)
      Converts Japanese Kanji/Hiragana/Katakana to Hepburn romanization.

Mixed-language lines (e.g. "I NEED U 나를 잊어줘") are handled
token-by-token: Latin tokens are left unchanged; non-Latin tokens
are romanized and inserted back in-place.
"""

import re
import logging
from typing import Optional

from config import PipelineConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy library loaders — only import what is actually needed
# ---------------------------------------------------------------------------

def _load_korean_romanizer():
    try:
        from korean_romanizer.romanizer import Romanizer
        return Romanizer
    except ImportError as exc:
        raise ImportError(
            "korean-romanizer is required for Korean romanization. "
            "Install with: pip install korean-romanizer"
        ) from exc


def _load_kakasi():
    try:
        import pykakasi
        kks = pykakasi.kakasi()
        return kks
    except ImportError as exc:
        raise ImportError(
            "pykakasi is required for Japanese romanization. "
            "Install with: pip install pykakasi"
        ) from exc


# ---------------------------------------------------------------------------
# Token-level helpers
# ---------------------------------------------------------------------------


def _is_hangul_char(ch: str) -> bool:
    cp = ord(ch)
    return 0xAC00 <= cp <= 0xD7A3 or 0x1100 <= cp <= 0x11FF


def _is_japanese_char(ch: str) -> bool:
    cp = ord(ch)
    return (
        0x3040 <= cp <= 0x30FF   # hiragana + katakana
        or 0x4E00 <= cp <= 0x9FFF  # CJK (kanji)
    )


def _split_by_script(text: str) -> list[tuple[str, str]]:
    """
    Split text into (token, script) pairs where script is
    'hangul', 'japanese', or 'latin'.
    Consecutive chars of the same script are merged.
    """
    tokens = []
    current_script = None
    current_buf = []

    for ch in text:
        if _is_hangul_char(ch):
            script = "hangul"
        elif _is_japanese_char(ch):
            script = "japanese"
        else:
            script = "latin"

        if script != current_script:
            if current_buf:
                tokens.append(("".join(current_buf), current_script))
            current_buf = [ch]
            current_script = script
        else:
            current_buf.append(ch)

    if current_buf:
        tokens.append(("".join(current_buf), current_script))

    return tokens


# ---------------------------------------------------------------------------
# Romanizer class
# ---------------------------------------------------------------------------

class LyricsRomanizer:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self._korean_romanizer_cls = None
        self._kakasi = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def romanize(self, lyrics: str, detected_language: str) -> Optional[str]:
        """
        Romanize lyrics based on the detected language.

        Returns the romanized string, or None if romanization is not
        applicable (i.e. the text is already entirely Latin-script).
        """
        needs_romanization = detected_language in (
            "korean", "japanese", "mixed_ko_en", "mixed_ja_en"
        )

        if not needs_romanization and not self.config.always_include_romanized:
            logger.debug("Skipping romanization — language is '%s'.", detected_language)
            return None

        if detected_language in ("korean", "mixed_ko_en"):
            return self._romanize_korean_mixed(lyrics)
        if detected_language in ("japanese", "mixed_ja_en"):
            return self._romanize_japanese_mixed(lyrics)

        # already Latin
        return lyrics

    # ------------------------------------------------------------------
    # Korean
    # ------------------------------------------------------------------

    def _get_korean_romanizer(self):
        if self._korean_romanizer_cls is None:
            self._korean_romanizer_cls = _load_korean_romanizer()
        return self._korean_romanizer_cls

    def _romanize_korean_token(self, token: str) -> str:
        Romanizer = self._get_korean_romanizer()
        try:
            return Romanizer(token).romanize()
        except Exception as exc:
            logger.warning("Korean romanization error on token '%s': %s", token, exc)
            return token  # fallback: return original

    def _romanize_korean_mixed(self, text: str) -> str:
        lines = text.split("\n")
        romanized_lines = []
        for line in lines:
            tokens = _split_by_script(line)
            parts = []
            for token, script in tokens:
                if script == "hangul":
                    parts.append(self._romanize_korean_token(token))
                else:
                    parts.append(token)
            romanized_lines.append("".join(parts))
        return "\n".join(romanized_lines)

    # ------------------------------------------------------------------
    # Japanese
    # ------------------------------------------------------------------

    def _get_kakasi(self):
        if self._kakasi is None:
            self._kakasi = _load_kakasi()
        return self._kakasi

    def _romanize_japanese_token(self, token: str) -> str:
        kks = self._get_kakasi()
        try:
            result = kks.convert(token)
            return " ".join(item["hepburn"] for item in result)
        except Exception as exc:
            logger.warning("Japanese romanization error on token '%s': %s", token, exc)
            return token

    def _romanize_japanese_mixed(self, text: str) -> str:
        lines = text.split("\n")
        romanized_lines = []
        for line in lines:
            tokens = _split_by_script(line)
            parts = []
            for token, script in tokens:
                if script == "japanese":
                    parts.append(self._romanize_japanese_token(token))
                else:
                    parts.append(token)
            romanized_lines.append("".join(parts))
        return "\n".join(romanized_lines)
