from __future__ import annotations
"""
Lyrics Pipeline - Main Orchestrator
Fetches, romanizes, translates, and structures song lyrics.
"""

import os
import json
import logging
import time
from pathlib import Path
from typing import Optional

from config import PipelineConfig
from step1_fetch import LyricsFetcher
from step2_romanize import LyricsRomanizer
from step3_translate import LyricsTranslator
from step4_structure import LyricsStructurer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline")


def run_pipeline(
    songs: list[dict],
    config: PipelineConfig,
    output_path: Optional[str] = None,
) -> list[dict]:
    """
    Execute the full 4-step lyrics pipeline.

    Args:
        songs: List of dicts with 'title' and 'artist' keys.
        config: PipelineConfig instance with API credentials and options.
        output_path: Optional file path to write the final JSON output.

    Returns:
        List of structured song objects ready for line-by-line display.
    """
    fetcher = LyricsFetcher(config)
    romanizer = LyricsRomanizer(config)
    translator = LyricsTranslator(config)
    structurer = LyricsStructurer(config)

    results = []

    for i, song in enumerate(songs, 1):
        title = song.get("title", "Unknown")
        artist = song.get("artist", "Unknown")
        logger.info("[%s/%s] Processing: %s - %s", i, len(songs), artist, title)

        try:
            # Step 1 - Fetch raw lyrics
            raw = fetcher.fetch(title, artist)
            if raw is None:
                logger.warning("  Skipping — lyrics not found.")
                results.append(structurer.make_error_entry(title, artist, "lyrics_not_found"))
                continue

            # Step 2 - Romanize (no-op for already-Roman scripts)
            romanized = romanizer.romanize(raw["lyrics"], raw["detected_language"])

            # Step 3 - Translate
            translated = translator.translate(raw["lyrics"], raw["detected_language"])

            # Step 4 - Structure into final JSON
            structured = structurer.structure(
                title=raw["title"],
                artist=raw["artist"],
                original_lyrics=raw["lyrics"],
                romanized_lyrics=romanized,
                translated_lyrics=translated,
                source_language=raw["detected_language"],
                target_language=config.target_language,
                metadata=raw.get("metadata", {}),
            )

            results.append(structured)
            logger.info("  Done: %d lines structured.", len(structured["lines"]))

        except Exception as exc:
            logger.error("  Failed: %s", exc, exc_info=True)
            results.append(structurer.make_error_entry(title, artist, str(exc)))

        # Polite delay between songs to respect API rate limits
        if i < len(songs):
            time.sleep(config.request_delay_seconds)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(
            json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        logger.info("Output written to %s", output_path)

    return results


def main():
    cfg = PipelineConfig(
        target_language="EN",
        romanization_backend="auto",
    )

    # New corpus from user image
    SONG_CORPUS = [
        {"title": "No More Dream", "artist": "BTS"},
        {"title": "Jump", "artist": "BTS"},
        {"title": "Pink Venom", "artist": "BLACKPINK"},
        {"title": "Hype Boy", "artist": "NewJeans"},
        {"title": "MIROH", "artist": "Stray Kids"},
        {"title": "Black Sorrow", "artist": "Park Byeong Hoon"},
        {"title": "Celebrity", "artist": "IU"},
        {"title": "Idol", "artist": "YOASOBI"},
        {"title": "Usseewa", "artist": "Ado"},
        {"title": "GO!!!", "artist": "FLOW"},
    ]

    output_dir = "results"
    output_file = os.path.join(output_dir, "lyrics_output.json")
    
    output = run_pipeline(SONG_CORPUS, cfg, output_path=output_file)
    print(f"\nPipeline complete. {len(output)} songs processed.")


if __name__ == "__main__":
    main()
