# Lyrics Processing Pipeline

A robust, multi-step pipeline for fetching, romanizing, and translating song lyrics. Optimized for K-Pop and J-Pop, featuring character-based language detection and batch translation.

## Features

- **Genius API Integration**: Searches and fetches raw lyrics with automatic header/metadata cleaning.
- **Romanization**: Converts Korean (Hangul) and Japanese (Kana/Kanji) to Latin script.
- **DeepL Translation**: Optional batch translation to English (or other target languages).
- **Graceful Failbacks**: Works without API keys (skips translation/fetch) and handles transient errors with retries.
- **Structured JSON Output**: Clean, line-by-line schema ready for vocal-training apps.

## Setup

1.  Clone the repository.
2.  Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3.  Create a `.env` file from the example:

    ```bash
    cp .env.example .env
    ```

4.  Add your API credentials to `.env`.

## Usage

Run the pipeline with the sample corpus defined in `pipeline.py`:

```bash
python pipeline.py
```

The output will be saved to `results/lyrics_output.json`.

## Project Structure

-   `pipeline.py`: Main orchestrator.
-   `step1_fetch.py`: Genius API interaction and cleaning.
-   `step2_romanize.py`: Script detection and romanization.
-   `step3_translate.py`: DeepL translation.
-   `step4_structure.py`: JSON schema construction.
-   `config.py`: Centralized configuration and .env loading.
-   `tests/`: Unit test suite.
