import sys
import os
import json
import argparse
from typing import List

# Force UTF-8 encoding for stdout/stderr to handle non-ASCII characters on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

from config import PipelineConfig
from pipeline import process_song, run_pipeline

def parse_song_string(s: str) -> dict:
    """Parse 'Artist - Title' into a dict."""
    if " - " in s:
        artist, title = s.split(" - ", 1)
        return {"artist": artist.strip(), "title": title.strip()}
    return {"artist": "Unknown", "title": s.strip()}

def main():
    parser = argparse.ArgumentParser(
        description="Lyrics Pipeline CLI - Process song lyrics, romanize and translate."
    )
    
    # Modes
    parser.add_argument(
        "song", 
        nargs="?", 
        help="Single song in 'Artist - Title' format."
    )
    parser.add_argument(
        "--songs", 
        help="Comma-separated list of 'Artist - Title' strings."
    )
    parser.add_argument(
        "--file", 
        help="Path to a JSON file containing a list of songs: [{'title': '...', 'artist': '...'}, ...]"
    )
    
    # Options
    parser.add_argument(
        "--output", 
        "-o", 
        help="Save results to this JSON file."
    )
    parser.add_argument(
        "--target", 
        default="EN", 
        help="Target language for translation (default: EN)."
    )
    parser.add_argument(
        "--no-print", 
        action="store_true", 
        help="Do not print JSON to stdout."
    )

    args = parser.parse_args()

    # Load config
    config = PipelineConfig(target_language=args.target, request_delay_seconds=0)
    
    songs_to_process = []

    # 1. Single song
    if args.song:
        songs_to_process.append(parse_song_string(args.song))
    
    # 2. Batch list
    if args.songs:
        parts = [p.strip() for p in args.songs.split(",")]
        for p in parts:
            songs_to_process.append(parse_song_string(p))
            
    # 3. File
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                songs_to_process.extend(data)
            else:
                songs_to_process.append(data)

    if not songs_to_process:
        parser.print_help()
        sys.exit(0)

    # Process
    if len(songs_to_process) == 1:
        s = songs_to_process[0]
        result = process_song(s["title"], s["artist"], config)
        results = [result]
    else:
        results = run_pipeline(songs_to_process, config)

    # Output
    output_json = json.dumps(results, indent=2, ensure_ascii=False)
    
    if not args.no_print:
        # Use buffer.write for robust UTF-8 output in various terminal environments
        sys.stdout.buffer.write(output_json.encode('utf-8'))
        sys.stdout.buffer.write(b'\n')
        sys.stdout.buffer.flush()
        
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"\nResults saved to {args.output}")

if __name__ == "__main__":
    main()
