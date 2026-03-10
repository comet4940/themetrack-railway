# ThemeTrack

Real-time stock dashboard tracking trending investment themes. Powered by Finnhub, served by a pure Python server.

## Deploy to Railway (free)

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "initial"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/themetrack.git
git push -u origin main
```

### 2. Deploy on Railway
1. Go to railway.app -> New Project -> Deploy from GitHub repo
2. Select your themetrack repo
3. Railway auto-detects the Procfile and deploys

### 3. Add your Finnhub API key
1. Railway dashboard -> your project -> Variables
2. Add: FINNHUB_API_KEY = your key from finnhub.io/dashboard
3. Railway auto-redeploys on save

### 4. Get your public URL
Railway gives you a URL like https://themetrack-production.up.railway.app

## Run Locally

```bash
export FINNHUB_API_KEY=your_key_here
python3 server.py
# Open http://localhost:8080
```

## Files

- server.py      Python server - fetches Finnhub, serves dashboard
- index.html     Dashboard frontend
- Procfile       Tells Railway: python3 server.py
- runtime.txt    Pins Python 3.11
- requirements.txt  Empty - no pip deps needed

## Notes
- Finnhub free tier: 60 req/min. Initial load ~2 min for 97 tickers.
- Not financial advice.
