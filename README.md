<p align="center">
  <img src="favicon.png" alt="LyrFlow Logo" width="80" />
</p>

<h1 align="center">🎵 LyrFlow</h1>

<p align="center">
  <strong>Instant lyrics romanization & translation powered by AI</strong><br/>
  <em>Built for the Aivancity Hackathon 2026</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Flask-Backend-000000?style=for-the-badge&logo=flask&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=for-the-badge&logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/PHP-Hostinger-777BB4?style=for-the-badge&logo=php&logoColor=white" />
</p>

---

## ✨ What is LyrFlow?

LyrFlow is a **web application** that takes any song (artist + title) and instantly returns:

| Feature | Description |
|---|---|
| 🌍 **Language Detection** | Automatically identifies the real language — Korean, Japanese, Punjabi, Hindi, Spanish, and more |
| 🔤 **Romanization** | Converts non-Latin scripts (한글, ひらがな, 漢字…) into readable Latin characters |
| 🇫🇷 **French Translation** | Every single line is translated to French, no matter the source language |
| ⚡ **Parallel Processing** | Lyrics are split into chunks and processed simultaneously for speed |

---

## 🏗️ Architecture

```
┌─────────────┐       ┌──────────────┐       ┌───────────────────┐
│   Frontend   │──────▶│  Flask / PHP │──────▶│  OpenAI GPT-4o    │
│  (HTML/JS)   │       │   Backend    │       │     mini          │
└─────────────┘       └──────┬───────┘       └───────────────────┘
                              │
                     ┌────────▼────────┐
                     │  lyrics.ovh API  │
                     │  (Lyrics Fetch)  │
                     └─────────────────┘
```

**Flow:**
1. User enters **Artist** + **Song Title**
2. Backend fetches raw lyrics from `lyrics.ovh`
3. Lyrics are cleaned & split into **chunks of 20 lines**
4. Each chunk is sent to **OpenAI GPT-4o-mini** in parallel (via `ThreadPoolExecutor`)
5. AI detects language, romanizes, and translates each line
6. Results are assembled and sent back to the beautiful frontend

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- An [OpenAI API key](https://platform.openai.com/api-keys)

### Installation

```bash
# Clone the repository
git clone https://github.com/Siddharth1254/alttrust-hackathon.git
cd alttrust-hackathon

# Install dependencies
pip install flask openai requests python-dotenv loguru

# Set your API key
echo OPENAI_API_KEY=sk-your-key-here > .env
```

### Run the Web App

```bash
python app.py
```

Then open **http://127.0.0.1:5000** in your browser. 🎉

### Run the CLI Pipeline

```bash
# French translation (default)
python pipeline.py --artist "BTS" --title "Dynamite"

# English translation
python pipeline.py --artist "BLACKPINK" --title "How You Like That" --lang english

# Save output to a file
python pipeline.py --artist "Karan Aujla" --title "Boyfriend" --lang english -o output/result.json
```

---

## 📁 Project Structure

```
alttrust-hackathon/
├── app.py                      # 🖥️  Flask web server (main backend)
├── pipeline.py                 # ⚙️  CLI pipeline (standalone usage)
├── prefetch.py                 # 📦  Demo song pre-cacher
├── templates/
│   └── index.html              # 🎨  Web UI (local version)
├── static/
│   └── favicon.svg             # 🎵  App icon
├── hostinger_source_code/      # 🌐  Production deployment (Hostinger)
│   ├── index.html              # 🎨  Web UI (production version)
│   ├── api.php                 # 🖥️  PHP backend (mirrors app.py)
│   ├── .htaccess               # ⚙️  Apache URL rewriting
│   └── favicon.svg             # 🎵  App icon
├── .env                        # 🔐  API keys (not committed)
├── .gitignore                  # 🚫  Git exclusion rules
└── README.md                   # 📖  You are here!
```

---

## 🎯 Example Songs to Test

| Genre | Artist | Song | Expected Language |
|-------|--------|------|-------------------|
| 🇰🇷 K-Pop | BTS | Dynamite | English |
| 🇰🇷 K-Pop | BLACKPINK | How You Like That | Korean + English |
| 🇰🇷 K-Pop | NewJeans | Super Shy | Korean + English |
| 🇯🇵 J-Pop | LiSA | Gurenge | Japanese |
| 🇯🇵 J-Pop | Kenshi Yonezu | Kick Back | Japanese |
| 🇮🇳 Punjabi | Karan Aujla | Boyfriend | Punjabi (romanized) |
| 🇰🇷 K-Pop | PSY | Gangnam Style | Korean |

---

## 🧠 How the AI Prompt Works

LyrFlow uses a **carefully crafted prompt** that instructs GPT-4o-mini to:

1. **Detect the real language** — not just the script. Romanized Punjabi in Latin characters won't be misclassified as English.
2. **Support any language** via ISO 639-1 codes (`ko`, `ja`, `pa`, `hi`, `es`, `ar`, `zh`…)
3. **Always translate** — every line gets a French (or English) translation, no exceptions.
4. **Return structured JSON** — enabling clean parsing and display in the frontend.

```json
{
  "lyrics": [
    {
      "line": "오늘 밤 주인공은 나야 나",
      "language": "ko",
      "romanized": "oneul bam juingongeun naya na",
      "translation": "Tonight, the star is me, me"
    }
  ]
}
```

---

## 🌐 Deployment (Hostinger)

The `hostinger_source_code/` directory contains a **PHP mirror** of the Flask backend, ready for shared hosting:

1. Upload the contents of `hostinger_source_code/` to your web root
2. Set your OpenAI API key in `api.php` (line 19)
3. Ensure `.htaccess` URL rewriting is enabled
4. Visit your domain — done! ✅

---

## 👥 Team

Built with ❤️ by **Team AltTrust** for the **Aivancity Hackathon 2026**.

---

## 📜 License

This project was created for educational and hackathon purposes.
