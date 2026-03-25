"""Pre-fetch and cache demo songs for instant display."""
import sys, io, json, requests, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from bs4 import BeautifulSoup
from korean_romanizer.romanizer import Romanizer
import pykakasi
from deep_translator import GoogleTranslator
from langdetect import detect, DetectorFactory
from pathlib import Path

DetectorFactory.seed = 0
kakasi_inst = pykakasi.kakasi()

CLIENT_ID = "Aj3L9UzE8CKlX7qYAP7msmHeKKatxacD66WEDc-UDp04MaswjNMKQTYZxC18rEKL"
CLIENT_SECRET = "TxkZclv67qbNdF2g9HqHFaO7-QD4Qqx09n7D1kmD_Z47gUpX9nO_lMUKmKHdZSucmYZpPzDdSjihKOkJ-xe97g"

DEMOS = [
    {"query": "BTS No More Dream", "expected_lang": "ko"},
    {"query": "IU Celebrity", "expected_lang": "ko"},
    {"query": "Stray Kids MIROH", "expected_lang": "ko"},
    {"query": "FLOW GO", "expected_lang": "ja"},
    {"query": "Ado Usseewa", "expected_lang": "ja"},
]

def get_token():
    resp = requests.post("https://api.genius.com/oauth/token", data={
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
    })
    return resp.json()["access_token"]

def search(query, token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get("https://api.genius.com/search", params={"q": query}, headers=headers, timeout=10)
    skip = ["translation", "romanization", "traducción", "traduction", "перевод", "übersetzung", "tradução"]
    for hit in resp.json()["response"]["hits"]:
        r = hit["result"]
        if any(kw in r["full_title"].lower() for kw in skip):
            continue
        if "genius" in r["primary_artist"]["name"].lower():
            continue
        return {
            "url": r["url"], "title": r["title"],
            "artist": r["primary_artist"]["name"],
            "thumbnail": r.get("song_art_image_thumbnail_url", ""),
        }
    return None

def scrape(url):
    resp = requests.get(url, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    containers = soup.find_all("div", attrs={"data-lyrics-container": "true"})
    if not containers: return None
    parts = []
    for c in containers:
        for br in c.find_all("br"): br.replace_with("\n")
        parts.append(c.get_text())
    return "\n".join(parts)

def clean(raw):
    lines = raw.split('\n')
    cleaned = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        if re.match(r'^\[.*\]$', line): continue
        if 'Contributors' in line or 'Read More' in line: continue
        if i == 0 and 'Lyrics' in line: continue
        line = re.sub(r'\d*Embed$', '', line).strip()
        if line: cleaned.append(line)
    return cleaned

def detect_lang(text):
    has_hangul = bool(re.search(r'[\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F]', text))
    has_jp = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text))
    has_cjk = bool(re.search(r'[\u4E00-\u9FFF]', text))
    has_latin = bool(re.search(r'[a-zA-Z]{2,}', text))
    if has_hangul and has_latin: return "ko-mixed"
    if (has_jp or (has_cjk and not has_hangul)) and has_latin: return "ja-mixed"
    if has_hangul: return "ko"
    if has_jp or (has_cjk and not has_hangul): return "ja"
    if has_latin: return "en"
    try: return {"ko":"ko","ja":"ja"}.get(detect(text), "en")
    except: return "unknown"

def romanize(text, lang):
    if lang == "en": return text
    if lang == "ko": return Romanizer(text).romanize()
    if lang == "ja": return " ".join(i['hepburn'] for i in kakasi_inst.convert(text))
    if "mixed" in lang:
        st = lang.replace("-mixed","")
        parts = re.split(r'([a-zA-Z][a-zA-Z\s\'\.!\?,]*[a-zA-Z]|[a-zA-Z])', text)
        rp = []
        for p in parts:
            if not p.strip(): continue
            elif re.match(r'^[a-zA-Z\s\'\.!\?,]+$', p): rp.append(p.strip())
            elif st == "ko": rp.append(Romanizer(p).romanize().strip())
            else: rp.append(" ".join(i['hepburn'] for i in kakasi_inst.convert(p)).strip())
        return " ".join(x for x in rp if x)
    return text

def process(raw):
    lines = clean(raw)
    langs = [detect_lang(l) for l in lines]
    counts = {"ko":0,"ja":0,"en":0}
    for la in langs:
        b = la.replace("-mixed","")
        if b in counts: counts[b] += 1
    dominant = max(counts, key=counts.get)
    roms = [romanize(l, la) for l, la in zip(lines, langs)]

    # Batch translate
    ko_items = [(i,t) for i,(t,l) in enumerate(zip(lines,langs)) if l in ("ko","ko-mixed")]
    ja_items = [(i,t) for i,(t,l) in enumerate(zip(lines,langs)) if l in ("ja","ja-mixed")]
    translations = [None]*len(lines)
    for items, src in [(ko_items,'ko'),(ja_items,'ja')]:
        if not items: continue
        idxs, txts = zip(*items)
        try:
            results = GoogleTranslator(source=src, target='fr').translate_batch(list(txts))
            for idx, val in zip(idxs, results): translations[idx] = val
        except:
            tr = GoogleTranslator(source=src, target='fr')
            for idx, txt in zip(idxs, txts):
                try: translations[idx] = tr.translate(txt)
                except: pass

    processed = []
    for line, rom, lang, tr in zip(lines, roms, langs, translations):
        entry = {"line": line, "romanized": rom, "language": lang}
        if tr: entry["translation"] = tr
        processed.append(entry)

    return {"language": dominant, "lyrics": processed, "lang_counts": counts}


token = get_token()
print("Token OK\n")

cache = {}
for demo in DEMOS:
    print(f"Fetching: {demo['query']}...")
    info = search(demo["query"], token)
    if not info:
        print(f"  NOT FOUND\n")
        continue

    print(f"  Found: {info['artist']} - {info['title']}")
    raw = scrape(info["url"])
    if not raw:
        print(f"  No lyrics\n")
        continue

    result = process(raw)
    result["title"] = info["title"]
    result["artist"] = info["artist"]
    result["thumbnail"] = info["thumbnail"]

    key = f"{info['artist']}||{info['title']}"
    cache[key] = result
    print(f"  -> {result['language']}, {len(result['lyrics'])} lines\n")

out = Path("static/demo_cache.json")
with open(out, 'w', encoding='utf-8') as f:
    json.dump(cache, f, ensure_ascii=False, indent=2)

print(f"\nSaved {len(cache)} songs to {out}")
