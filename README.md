# Morning Mutation - AI News & Weather Broadcast

An automated, AI-driven morning broadcast system that scrapes the latest news, clusters related stories, and generates a witty audio script hosted by 'Igor' (News) and 'Olivia' (Weather).

## 🚀 Features

- **Robust Scraping**: Uses `curl-cffi` for TLS impersonation to bypass 403 Forbidden blocks on major news sites.
- **Intelligent Clustering**: Groups similar articles from different sources using TF-IDF and Agglomerate Clustering to avoid repetitive reporting.
- **Categorical News**: Automatically categorizes stories into topics like AI, Tech, Politics, and World News.
- **Double LLM Pass**: 
    1. **Synthesizer**: Consolidates multiple sources into a single objective summary.
    2. **Scriptwriter**: Converts summaries into a punchy, humorous broadcast script.
- **Dynamic Weather**: Fetches local forecasts via Open-Meteo and generates a conversational weather report.
- **High-Quality TTS**: Uses Inworld AI's character voices for distinct, expressive host personalities.
- **Web Dashboard**: Modern UI to read the summaries while listening to the broadcast.

## 🛠️ Setup

### Prerequisites
- Python 3.9+
- `ffmpeg` installed on your system (for audio mixing)

### Installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your API keys:
   ```env
   OPENROUTER_API_KEY=your_key_here
   INWORLD_API_KEY=your_key_here
   ```
4. Configure your sources and location in `config.yaml`.

## 📖 Usage

### Running the Pipeline
Generate today's broadcast by running:
```bash
python main.py
```
This will:
1. Scrape latest articles.
2. Synthesize summaries.
3. Generate TTS audio in `output/morning_mutation.mp3`.
4. Export metadata to `output/broadcast_data.json`.

### Viewing the Dashboard
Open the dashboard to view summaries and listen to the audio:
```bash
# Start a simple server
python -m http.server 8000
# Visit http://localhost:8000/frontend in your browser
```

## 🏗️ Docker Deployment

The simplest way to run Morning Mutation is via Docker.

1. **Setup Environment**: Ensure `.env` is populated.
2. **Start the Web Dashboard**:
   ```bash
   docker compose up -d morning-mutation-web
   ```
   The dashboard will be available at `http://localhost:37542/frontend`.
3. **Run the Pipeline**:
   ```bash
   docker compose up --build morning-mutation
   ```
   This will scrape news, generate audio, and export data to the `output/` volume shared with the web server.

## ⏰ Automation (Cron)

To have your broadcast ready every morning, add a cron job to your host system:

1. Open crontab: `crontab -e`
2. Add a line to run the pipeline at 7:00 AM daily (adjust path to your project):
   ```bash
   0 7 * * * cd /path/to/morning-mutation && /usr/local/bin/docker-compose up morning-mutation >> /var/log/morning-mutation.log 2>&1
   ```

## 🏗️ Architecture

- `main.py`: The orchestrator script.
- `src/scraper.py`: Handles RSS fetching and article scraping with TLS bypass and keyword filtering.
- `src/cluster.py`: Categorizes and clusters articles.
- `src/summarizer.py`: LLM logic for synthesis and script generation.
- `src/weather.py`: Fetching and drafting the conversational weather report.
- `src/tts.py`: Audio generation via Inworld AI.
- `src/audio_mixer.py`: Splicing news, weather, and commercials.
- `frontend/`: The glassmorphism vanilla CSS/JS web interface.

## 📜 License
MIT
