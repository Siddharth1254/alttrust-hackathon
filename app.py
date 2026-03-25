"""
LyrFlow - SaaS Web Interface
Uses lyrics.ovh API + OpenAI GPT-4o-mini for romanization & translation
"""
import json
import re
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, jsonify, request
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")

# ── Config ──────────────────────────────────────────────────────────────────

OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_KEY)

CACHE_PATH = Path("static/demo_cache.json")


# ── Lyrics.ovh API ──────────────────────────────────────────────────────────

def fetch_lyrics(artist, title):
    """Fetch lyrics from lyrics.ovh API."""
    url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
    resp = requests.get(url, timeout=15)
    if resp.status_code == 200:
        lyrics = resp.json().get("lyrics", "")
        return lyrics if lyrics else None
    return None


def clean_lyrics(raw):
    """Clean raw lyrics into list of non-empty lines."""
    lines = []
    for line in raw.split('\n'):
        line = line.strip()
        if not line:
            continue
        # Remove section headers like [Verse 1], [Chorus], [Rap Monster]
        if re.match(r'^\[.*\]$', line):
            continue
        lines.append(line)
    return lines


# ── OpenAI Processing ──────────────────────────────────────────────────────

CHUNK_SIZE = 20


def _process_chunk(chunk_lines):
    """Process one chunk with OpenAI."""
    lyrics_text = "\n".join(chunk_lines)

    prompt = f"""Tu es un expert en musique internationale et en linguistique.

Pour chaque ligne de paroles ci-dessous :
1. Detecte la VRAIE langue (ko, ja, en, hi, pa, es, fr, ar, zh, ou autre code ISO 639-1). ATTENTION: du texte en alphabet latin peut etre du pendjabi romanisé, du hindi romanisé, de l'espagnol, etc. Ne classe PAS automatiquement tout texte latin comme "en". Analyse le vocabulaire et la grammaire pour identifier la vraie langue.
2. Si la ligne contient un mélange de langues, utilise le suffixe "-mixed" (ex: "ko-mixed", "pa-mixed")
3. Donne la romanisation si la ligne contient des caractères non-latins (coréen, japonais, chinois, arabe, etc.). Si la ligne est DEJA en alphabet latin, romanized = la ligne elle-meme.
4. Traduis TOUJOURS en français, quelle que soit la langue source. Meme si la ligne est en anglais, traduis-la.

Reponds UNIQUEMENT en JSON valide avec cette structure exacte :
{{"lyrics": [{{"line": "texte original", "language": "code_langue", "romanized": "romanisation", "translation": "traduction française"}}]}}

- Utilise la romanisation révisée pour le coréen, Hepburn pour le japonais
- La traduction doit TOUJOURS etre presente et en français, jamais null

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

    result = json.loads(resp.choices[0].message.content)
    return result.get("lyrics", [])


def process_with_openai(lyrics_lines):
    """Split lyrics into chunks and process in parallel."""
    chunks = [lyrics_lines[i:i + CHUNK_SIZE] for i in range(0, len(lyrics_lines), CHUNK_SIZE)]

    if len(chunks) == 1:
        return _process_chunk(chunks[0])

    results = [None] * len(chunks)
    with ThreadPoolExecutor(max_workers=len(chunks)) as ex:
        futures = {ex.submit(_process_chunk, c): i for i, c in enumerate(chunks)}
        for f in as_completed(futures):
            idx = futures[f]
            try:
                results[idx] = f.result()
            except:
                results[idx] = []

    return [line for chunk in results if chunk for line in chunk]


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/demos')
def api_demos():
    """Return pre-cached demo songs."""
    if CACHE_PATH.exists():
        with open(CACHE_PATH, encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({})


@app.route('/api/process', methods=['POST'])
def api_process():
    """Fetch lyrics + process with OpenAI. Accepts {artist, title}."""
    data = request.get_json()
    artist = data.get("artist", "").strip()
    title = data.get("title", "").strip()

    if not artist or not title:
        return jsonify({"error": "Artist and title are required"}), 400

    # Check cache first
    cache_key = f"{artist}||{title}"
    if CACHE_PATH.exists():
        with open(CACHE_PATH, encoding='utf-8') as f:
            cache = json.load(f)
        if cache_key in cache:
            return jsonify(cache[cache_key])

    # Step 1: Fetch lyrics from lyrics.ovh
    raw = fetch_lyrics(artist, title)
    if not raw:
        return jsonify({"error": f"Lyrics not found for '{title}' by '{artist}'"}), 404

    # Step 2: Clean
    lines = clean_lyrics(raw)
    if not lines:
        return jsonify({"error": "No lyrics content found"}), 404

    # Step 3: Process with OpenAI (romanize + translate + detect)
    try:
        processed = process_with_openai(lines)
    except Exception as e:
        return jsonify({"error": f"OpenAI processing error: {str(e)}"}), 500

    # Compute language stats
    lang_counts = {"ko": 0, "ja": 0, "en": 0}
    for l in processed:
        base = l.get("language", "en").replace("-mixed", "")
        if base in lang_counts:
            lang_counts[base] += 1
    dominant = max(lang_counts, key=lang_counts.get)

    result = {
        "title": title,
        "artist": artist,
        "language": dominant,
        "lang_counts": lang_counts,
        "lyrics": processed,
    }

    return jsonify(result)


if __name__ == '__main__':
    print("LyrFlow running at http://127.0.0.1:5000")
    app.run(debug=False, port=5000)
