from __future__ import annotations
"""
Step 3 - Translate lyrics using DeepL or OpenAI GPT-4o mini.

Features:
  - Supports multiple backends (DeepL, OpenAI).
  - Preserves line-by-line structure.
  - Contextual translation for better poetic quality via LLM.
  - Graceful fallbacks and error handling.
"""

import logging
import re
import time
from typing import Optional, Union

import deepl
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from config import PipelineConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Line-level language check
# ---------------------------------------------------------------------------

_HANGUL_RE   = re.compile(r"[\uAC00-\uD7A3\u1100-\u11FF]")
_JAPANESE_RE = re.compile(r"[\u3040-\u30FF\u4E00-\u9FFF]")


def _line_needs_translation(line: str) -> bool:
    """Return True if the line contains any non-Latin script characters."""
    return bool(_HANGUL_RE.search(line) or _JAPANESE_RE.search(line))


# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------

def _chunk_text(text: str, max_chars: int) -> list[str]:
    """Split text into chunks of at most max_chars at paragraph boundaries."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para) + 2
        if current_len + para_len > max_chars and current:
            chunks.append("\n\n".join(current))
            current = [para]
            current_len = para_len
        else:
            current.append(para)
            current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks


# ---------------------------------------------------------------------------
# Translator class
# ---------------------------------------------------------------------------

class LyricsTranslator:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self._deepl_client: Optional[deepl.Translator] = None
        self._openai_client = None

    def _get_deepl_client(self) -> Optional[deepl.Translator]:
        if self._deepl_client is None:
            if not self.config.deepl_api_key:
                logger.warning("DeepL API key is missing.")
                return None
            self._deepl_client = deepl.Translator(self.config.deepl_api_key)
        return self._deepl_client

    def _get_openai_client(self):
        if self._openai_client is None:
            if not self.config.openai_api_key:
                logger.warning("OpenAI API key is missing.")
                return None
            if OpenAI is None:
                logger.error("OpenAI library not installed. pip install openai")
                return None
            self._openai_client = OpenAI(api_key=self.config.openai_api_key)
        return self._openai_client

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def translate(self, lyrics: str, detected_language: str) -> Optional[str]:
        """Translate lyrics to config.target_language using the selected backend."""
        target = self.config.target_language.upper()
        
        # Simple mapping for skip check
        mapping = {"korean": "KO", "japanese": "JA", "english": "EN"}
        source_hint = mapping.get(detected_language)
        if source_hint == target:
            return None

        backend = self.config.translation_backend.lower()
        if backend == "openai":
            return self._translate_openai(lyrics, detected_language, target)
        else:
            return self._translate_deepl(lyrics, detected_language, target)

    # ------------------------------------------------------------------
    # DeepL Implementation
    # ------------------------------------------------------------------

    def _translate_deepl(self, lyrics: str, detected_language: str, target: str) -> str:
        """Original DeepL translation logic."""
        source_lang_hint = self._map_language_deepl(detected_language)
        
        if detected_language in ("mixed_ko_en", "mixed_ja_en"):
            return self._translate_mixed_deepl(lyrics, source_lang_hint, target)

        return self._translate_block_deepl(lyrics, source_lang_hint, target)

    def _map_language_deepl(self, detected: str) -> Optional[str]:
        mapping = {"korean": "KO", "japanese": "JA", "english": "EN", "mixed_ko_en": "KO", "mixed_ja_en": "JA"}
        return mapping.get(detected)

    def _translate_block_deepl(self, text: str, source_lang: Optional[str], target_lang: str) -> str:
        chunks = _chunk_text(text, self.config.deepl_chunk_size)
        translated_chunks = []
        for chunk in chunks:
            translated_chunks.append(self._call_deepl(chunk, source_lang, target_lang))
        return "\n\n".join(translated_chunks)

    def _translate_mixed_deepl(self, text: str, source_lang: Optional[str], target_lang: str) -> str:
        lines = text.split("\n")
        foreign_lines = [(i, l) for i, l in enumerate(lines) if l.strip() and _line_needs_translation(l)]
        if not foreign_lines: return text

        client = self._get_deepl_client()
        if client is None: return text

        try:
            foreign_texts = [l for _, l in foreign_lines]
            kwargs = {"target_lang": target_lang}
            if source_lang: kwargs["source_lang"] = source_lang
            if self.config.deepl_formality != "default": kwargs["formality"] = self.config.deepl_formality

            results = client.translate_text(foreign_texts, **kwargs)
            res_lines = list(lines)
            for j, (orig_idx, _) in enumerate(foreign_lines):
                res_lines[orig_idx] = results[j].text
            return "\n".join(res_lines)
        except Exception as exc:
            logger.error("DeepL batch failed: %s", exc)
            return text

    def _call_deepl(self, text: str, src: Optional[str], tgt: str, attempt: int = 0) -> str:
        client = self._get_deepl_client()
        if client is None: return text
        try:
            kwargs = {"target_lang": tgt}
            if src: kwargs["source_lang"] = src
            if self.config.deepl_formality != "default": kwargs["formality"] = self.config.deepl_formality
            return client.translate_text(text, **kwargs).text
        except Exception as exc:
            if attempt < 2:
                time.sleep(1)
                return self._call_deepl(text, src, tgt, attempt + 1)
            logger.error("DeepL failed: %s", exc)
            return text

    # ------------------------------------------------------------------
    # OpenAI Implementation
    # ------------------------------------------------------------------

    def _translate_openai(self, lyrics: str, detected_language: str, target: str) -> str:
        """GPT-4o mini translation logic."""
        client = self._get_openai_client()
        if client is None:
            return lyrics

        try:
            prompt = (
                f"You are a professional lyrics translator. Translate the following {detected_language} song lyrics "
                f"into {target} while preserving the poetic meaning and line-by-line structure. "
                "Do not add any commentary, notes, or extra text. Just provide the translation."
            )
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": lyrics}
                ],
                temperature=0.3,
            )
            return response.choices[0].message.content or lyrics
        except Exception as exc:
            logger.error("OpenAI translation failed: %s", exc)
            return lyrics
