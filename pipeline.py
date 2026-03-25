"""
LyrFlow - CLI Pipeline
Usage:
    python pipeline.py --artist "BTS" --title "No More Dream"
    python pipeline.py --artist "IU" --title "Celebrity" --output output/iu.json
    python pipeline.py --artist "Ado" --title "Usseewa" --lang fr

Uses: lyrics.ovh API + OpenAI GPT-4o-mini
"""
import sys
import io
import json
import re
import argparse
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger
from openai import OpenAI

# UTF-8 on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ── Loguru config ───────────────────────────────────────────────────────────

logger.remove()  # Remove default handler
logger.add(sys.stderr, level="INFO",
           format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <cyan>{function}</cyan> - <level>{message}</level>")
logger.add("lyrflow.log", level="DEBUG", rotation="1 MB",
           format="{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {function}:{line} - {message}")

# ── Config ──────────────────────────────────────────────────────────────────

OPENAI_KEY = "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"

client = OpenAI(api_key=OPENAI_KEY)


# ── Step 1: Fetch lyrics from lyrics.ovh ────────────────────────────────────

def fetch_lyrics(artist: str, title: str) -> str | None:
    """Fetch lyrics from lyrics.ovh API."""
    url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
    logger.info(f"Fetching lyrics: {artist} - {title}")
    logger.debug(f"GET {url}")

    try:
        resp = requests.get(url, timeout=15)
        logger.debug(f"Response status: {resp.status_code}")

        if resp.status_code == 200:
            lyrics = resp.json().get("lyrics", "")
            if lyrics:
                logger.success(f"Got lyrics: {len(lyrics)} chars")
                return lyrics
            else:
                logger.warning("Response OK but lyrics field is empty")
                return None
        else:
            logger.error(f"lyrics.ovh returned {resp.status_code}: {resp.text[:200]}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return None


# ── Step 2: Clean lyrics ────────────────────────────────────────────────────

def clean_lyrics(raw: str) -> list[str]:
    """Clean raw lyrics into a list of non-empty, meaningful lines."""
    logger.info("Cleaning lyrics...")
    lines = []
    for line in raw.split('\n'):
        line = line.strip()
        if not line:
            continue
        if re.match(r'^\[.*\]$', line):
            logger.debug(f"Skipping section header: {line}")
            continue
        lines.append(line)

    logger.info(f"Cleaned: {len(lines)} lines")
    return lines


# ── Step 3: Process with OpenAI ─────────────────────────────────────────────

CHUNK_SIZE = 20  # lines per parallel OpenAI request


def _process_chunk(chunk_id: int, lines: list[str], target_lang: str) -> tuple[int, list[dict]]:
    """Process a single chunk of lyrics with OpenAI. Returns (chunk_id, results)."""
    lyrics_text = "\n".join(lines)
    logger.debug(f"Chunk {chunk_id}: sending {len(lines)} lines to OpenAI")

    prompt = f"""Tu es un expert en musique internationale et en linguistique.

Pour chaque ligne de paroles ci-dessous :
1. Detecte la VRAIE langue (ko, ja, en, hi, pa, es, fr, ar, zh, ou autre code ISO 639-1). ATTENTION: du texte en alphabet latin peut etre du pendjabi romanisé, du hindi romanisé, de l'espagnol, etc. Ne classe PAS automatiquement tout texte latin comme "en". Analyse le vocabulaire et la grammaire pour identifier la vraie langue.
2. Si la ligne contient un mélange de langues, utilise le suffixe "-mixed" (ex: "ko-mixed", "pa-mixed")
3. Donne la romanisation si la ligne contient des caractères non-latins (coréen, japonais, chinois, arabe, etc.). Si la ligne est DEJA en alphabet latin, romanized = la ligne elle-meme.
4. Traduis TOUJOURS en {target_lang}, quelle que soit la langue source. Meme si la ligne est en anglais, traduis-la.

Reponds UNIQUEMENT en JSON valide avec cette structure exacte :
{{"lyrics": [{{"line": "texte original", "language": "code_langue", "romanized": "romanisation", "translation": "traduction"}}]}}

- Utilise la romanisation révisée pour le coréen, Hepburn pour le japonais
- La traduction doit TOUJOURS etre presente et en {target_lang}, jamais null

PAROLES :
{lyrics_text}"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Tu es un assistant expert en linguistique et traduction musicale. Tu detectes avec precision la langue reelle des paroles, y compris les langues ecrites en alphabet latin comme le pendjabi romanise, le hindi romanise, l'espagnol, etc. Tu reponds uniquement en JSON valide."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        response_format={"type": "json_object"}
    )

    usage = resp.usage
    logger.debug(f"Chunk {chunk_id} done: {usage.total_tokens} tokens")

    result = json.loads(resp.choices[0].message.content)
    return chunk_id, result.get("lyrics", [])


def process_with_openai(lyrics_lines: list[str], target_lang: str = "français") -> list[dict]:
    """Split lyrics into chunks and process them in parallel with OpenAI."""
    total = len(lyrics_lines)

    # Split into chunks
    chunks = [lyrics_lines[i:i + CHUNK_SIZE] for i in range(0, total, CHUNK_SIZE)]
    logger.info(f"Sending {total} lines to OpenAI GPT-4o-mini ({len(chunks)} parallel chunks of ~{CHUNK_SIZE})")

    # Single chunk — no need for threading
    if len(chunks) == 1:
        _, result = _process_chunk(0, chunks[0], target_lang)
        logger.success(f"OpenAI returned {len(result)} processed lines")
        return result

    # Parallel execution
    results = [None] * len(chunks)
    with ThreadPoolExecutor(max_workers=len(chunks)) as executor:
        futures = {
            executor.submit(_process_chunk, i, chunk, target_lang): i
            for i, chunk in enumerate(chunks)
        }
        for future in as_completed(futures):
            try:
                chunk_id, processed = future.result()
                results[chunk_id] = processed
                logger.debug(f"Chunk {chunk_id} returned {len(processed)} lines")
            except Exception as e:
                chunk_id = futures[future]
                logger.error(f"Chunk {chunk_id} failed: {e}")
                results[chunk_id] = []

    # Flatten in order
    all_lines = []
    for r in results:
        if r:
            all_lines.extend(r)

    logger.success(f"OpenAI returned {len(all_lines)} processed lines (from {len(chunks)} chunks)")
    return all_lines


# ── Step 4: Build final output ──────────────────────────────────────────────

def build_output(artist: str, title: str, processed: list[dict]) -> dict:
    """Build the final structured JSON output."""
    logger.info("Building output...")

    lang_counts = {"ko": 0, "ja": 0, "en": 0}
    for l in processed:
        base = l.get("language", "en").replace("-mixed", "")
        if base in lang_counts:
            lang_counts[base] += 1

    dominant = max(lang_counts, key=lang_counts.get)
    logger.info(f"Language stats: {lang_counts} -> dominant: {dominant}")

    return {
        "title": title,
        "artist": artist,
        "language": dominant,
        "lang_counts": lang_counts,
        "lyrics": processed,
    }


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="LyrFlow - Lyrics Romanization & Translation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline.py --artist "BTS" --title "No More Dream"
  python pipeline.py --artist "IU" --title "Celebrity" --output result.json
  python pipeline.py --artist "Ado" --title "Usseewa" --lang français
        """
    )
    parser.add_argument("--artist", required=True, help="Artist name")
    parser.add_argument("--title", required=True, help="Song title")
    parser.add_argument("--output", "-o", default=None, help="Output JSON file path (default: stdout)")
    parser.add_argument("--lang", default="français", help="Target translation language (default: français)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG",
                   format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
        logger.add("lyrflow.log", level="DEBUG", rotation="1 MB")

    logger.info(f"=== LyrFlow Pipeline ===")
    logger.info(f"Artist: {args.artist}")
    logger.info(f"Title:  {args.title}")
    logger.info(f"Lang:   {args.lang}")

    # Step 1: Fetch
    raw = fetch_lyrics(args.artist, args.title)
    if not raw:
        logger.error("Could not fetch lyrics. Exiting.")
        sys.exit(1)

    # Step 2: Clean
    lines = clean_lyrics(raw)
    if not lines:
        logger.error("No lyrics lines after cleaning. Exiting.")
        sys.exit(1)

    # Step 3: Process with OpenAI
    processed = process_with_openai(lines, args.lang)

    # Step 4: Build output
    result = build_output(args.artist, args.title, processed)

    # Output
    output_json = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(output_json)
        logger.success(f"Saved to {output_path}")
    else:
        print(output_json)

    logger.success(f"Done! {len(processed)} lines processed.")


if __name__ == "__main__":
    main()
