import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from config import PipelineConfig
from pipeline import process_song
from step1_fetch import LyricsFetcher
from step2_romanize import LyricsRomanizer
from step3_translate import LyricsTranslator
from step4_structure import LyricsStructurer

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Lyrics Pipeline API",
    description="Search, Romanize, and Translate song lyrics on demand.",
    version="1.0.0"
)

# Shared config and components
config = PipelineConfig(target_language="EN", request_delay_seconds=0)
fetcher = LyricsFetcher(config)
romanizer = LyricsRomanizer(config)
translator = LyricsTranslator(config)
structurer = LyricsStructurer(config)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SongRequest(BaseModel):
    title: str
    artist: str

class ProcessRequest(BaseModel):
    songs: List[SongRequest]

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/process_single")
async def api_process_single(request: SongRequest):
    """Process a single song and return the structured JSON."""
    result = process_song(
        title=request.title,
        artist=request.artist,
        config=config,
        fetcher=fetcher,
        romanizer=romanizer,
        translator=translator,
        structurer=structurer
    )
    
    if result.get("error"):
        # We still return the error entry so the client knows which song failed
        return result
        
    return result

@app.post("/process")
async def api_process_batch(request: ProcessRequest):
    """Process a batch of songs."""
    results = []
    for song in request.songs:
        res = process_song(
            title=song.title,
            artist=song.artist,
            config=config,
            fetcher=fetcher,
            romanizer=romanizer,
            translator=translator,
            structurer=structurer
        )
        results.append(res)
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
