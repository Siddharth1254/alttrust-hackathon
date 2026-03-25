from __future__ import annotations
"""
Step 1 - Fetch raw lyrics from the Genius API (manual implementation).
"""

import json
import logging
import re
import time
import unicodedata
import urllib.request
import urllib.parse
from typing import Optional

from config import PipelineConfig

logger = logging.getLogger(__name__)


def _char_category(ch: str) -> str:
    """Return a broad script category for a single character."""
    cp = ord(ch)
    if 0xAC00 <= cp <= 0xD7A3 or 0x1100 <= cp <= 0x11FF or 0xA960 <= cp <= 0xA97F:
        return "hangul"
    if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0xF900 <= cp <= 0xFAFF:
        return "cjk"
    if 0x3040 <= cp <= 0x30FF:
        return "kana"
    if 0x0041 <= cp <= 0x007A:
        return "latin"
    return "other"


def detect_language(text: str) -> str:
    """Classify the dominant language of a lyrics block."""
    counts = {"hangul": 0, "cjk": 0, "kana": 0, "latin": 0, "other": 0}
    for ch in text:
        counts[_char_category(ch)] += 1

    total_meaningful = sum(counts.values()) - counts["other"]
    if total_meaningful == 0:
        return "unknown"

    hangul_ratio = counts["hangul"] / total_meaningful
    kana_ratio   = counts["kana"]   / total_meaningful
    cjk_ratio    = counts["cjk"]    / total_meaningful
    latin_ratio  = counts["latin"]  / total_meaningful

    if hangul_ratio > 0.4:
        return "korean" if latin_ratio < 0.2 else "mixed_ko_en"
    if (kana_ratio + cjk_ratio) > 0.3:
        return "japanese" if latin_ratio < 0.2 else "mixed_ja_en"
    if latin_ratio > 0.5:
        return "english"
    return "unknown"


# Final refined cleaning regexes
_SECTION_HEADER_RE = re.compile(r"^\[.*?\]\s*$", re.MULTILINE)
_CONTRIBUTOR_RE = re.compile(r"^\d+\s*Contributors?.*?(Translations|Lyrics|$)", re.IGNORECASE)
_TRANSLATIONS_HEADER_RE = re.compile(r"Translations.*?(Lyrics|$)", re.IGNORECASE)
_LANGUAGE_LIST_RE = re.compile(r"(한국어|ไทย|Italiano|فارسی|Magyar|Deutsch|Українська|Español|Português|Français|English|繁體中文|Romanization).*")
_YOU_MIGHT_ALSO_LIKE_RE = re.compile(r"You might also like.*", re.IGNORECASE)
_EMBED_RE = re.compile(r"\d*Embed.*?$", re.MULTILINE | re.DOTALL)
_GENIUS_FOOTER_RE = re.compile(r"(Expand\s*Credits|Tags|About|Song Bio|Ask a question|Genius is the ultimate source|Sign Up|How to Format Lyrics).*$", re.MULTILINE | re.DOTALL)

def clean_lyrics(raw: str, strip_headers: bool = True) -> str:
    """Remove Genius artifacts and normalise whitespace."""
    text = raw
    
    # Remove top meta
    text = _CONTRIBUTOR_RE.sub("", text)
    text = _TRANSLATIONS_HEADER_RE.sub("", text)
    text = _LANGUAGE_LIST_RE.sub("", text)
    
    # Remove middle meta (like "You might also like")
    text = _YOU_MIGHT_ALSO_LIKE_RE.sub("", text)
    
    # Remove bottom meta
    text = _EMBED_RE.sub("", text)
    text = _GENIUS_FOOTER_RE.sub("", text)
    
    if strip_headers:
        text = _SECTION_HEADER_RE.sub("", text)
    
    text = unicodedata.normalize("NFC", text)
    # Remove common short artifacts that escaped regex
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            cleaned_lines.append("")
            continue
        # Skip common non-lyric lines or lines that are just "Lyrics"
        if any(x in line.lower() for x in ["embed", "cancel", "how to format lyrics", "contributors", "read more"]):
            continue
        if line.lower() == "lyrics":
            continue
        cleaned_lines.append(line)
        
    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class LyricsFetcher:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self._token = config.genius_token
        if not self._token and config.genius_client_id and config.genius_client_secret:
            self._token = self._get_access_token(config.genius_client_id, config.genius_client_secret)

    def _get_access_token(self, client_id: str, client_secret: str) -> Optional[str]:
        """Request an access token via client_credentials grant."""
        token_url = "https://api.genius.com/oauth/token"
        payload = json.dumps({
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        }).encode("utf-8")

        req = urllib.request.Request(token_url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                return data.get("access_token")
        except Exception as e:
            logger.error("Failed to obtain Genius access token: %s", e)
            return None

    def fetch(self, title: str, artist: str) -> Optional[dict]:
        """Search and scrape lyrics for a song."""
        if not self._token:
            logger.error("No Genius token available.")
            return None

        query = urllib.parse.urlencode({"q": f"{artist} {title}"})
        search_url = f"https://api.genius.com/search?{query}"
        
        req = urllib.request.Request(search_url)
        req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                hits = data.get("response", {}).get("hits", [])
                if not hits:
                    return None
                
                # Try to find a better artist match
                best_hit = hits[0]["result"]
                artist_lower = artist.lower()
                # 1. Look for exact artist match without "Translation" in title
                for h in hits:
                    res = h["result"]
                    primary_artist = res["primary_artist"]["name"].lower()
                    if primary_artist == artist_lower and "translation" not in res["title"].lower():
                        best_hit = res
                        break
                else:
                    # 2. Look for partial artist match without "Translation"
                    for h in hits:
                        res = h["result"]
                        primary_artist = res["primary_artist"]["name"].lower()
                        if artist_lower in primary_artist and "translation" not in res["title"].lower():
                            best_hit = res
                            break
                
                song_data = best_hit
                song_url = song_data["url"]
                lyrics = self._scrape_lyrics(song_url)
                if not lyrics:
                    return None

                cleaned = clean_lyrics(lyrics, self.config.strip_section_headers)
                return {
                    "title": song_data["title"],
                    "artist": song_data["primary_artist"]["name"],
                    "lyrics": cleaned,
                    "detected_language": detect_language(cleaned),
                    "metadata": {
                        "genius_id": song_data["id"],
                        "genius_url": song_url,
                        "album": song_data.get("full_title"),
                        "year": song_data.get("release_date_for_display"),
                    }
                }
        except Exception as e:
            logger.error("Fetch failed for '%s - %s': %s", artist, title, e)
            return None

    def _scrape_lyrics(self, url: str) -> Optional[str]:
        """Fetch the Genius HTML and extract the lyrics."""
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            req.add_header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8")
            
            with urllib.request.urlopen(req) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                
                # Greedy match from first container until footer or script
                match = re.search(r'data-lyrics-container="true"[^>]*>(.*?)<div [^>]*class="[^"]*Lyrics__Footer', html, re.DOTALL)
                if not match:
                    match = re.search(r'data-lyrics-container="true"[^>]*>(.*?)<script', html, re.DOTALL)
                
                if not match:
                    pieces = re.findall(r'data-lyrics-container="true"[^>]*>(.*?)</div>', html, re.DOTALL)
                    full_html = "\n".join(pieces)
                else:
                    full_html = match.group(1)
                
                if not full_html.strip():
                    return None
                
                # Replace <br/> and clear tags
                lyrics = full_html.replace("<br/>", "\n").replace("<br>", "\n")
                lyrics = re.sub(r'<[^>]+>', '', lyrics)
                
                import html as html_parser
                lyrics = html_parser.unescape(lyrics)
                return lyrics.strip()
        except Exception as e:
            logger.error("Scraping failed for %s: %s", url, e)
            return None
