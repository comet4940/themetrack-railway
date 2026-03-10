#!/usr/bin/env python3
"""
ThemeTrack server — Finnhub edition.
Usage: python3 server.py
Then open: http://localhost:8080
"""

import json, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError

import os
PORT = int(os.environ.get('PORT', 8080))  # Railway injects $PORT automatically
CACHE_TTL = 60
API_KEY = os.environ.get('FINNHUB_API_KEY', '')  # Set this in Railway environment variables
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ALL_TICKERS = [
    'AMD','AMPX','BABA','BIDU','BITF','CIFR','CLSK','CORZ','CRWV','EOSE',
    'GOOGL','HUT','IREN','LAES','NBIS','NUAI','NVDA','NVTS','PATH','POWL',
    'RR','SERV','SNDK','TE','TSLA','TSM','WDC','ZETA',
    'AMAT','LRCX','MRAM','MRVL','MU','NTAP','PSTG','RMBS','SIMO','STX',
    'AMTM','AVAV','BWXT','DPRO','ESLT','KRKNF','KRMN','KTOS','LPTH','MOB',
    'MRCY','ONDS','OSS','PLTR','PRZO','RCAT','TDY','UMAC',
    'CRDO','IBRX','IONQ','IONR','LAC','MP','NAK','NET','OPTT','PPTA',
    'RZLT','SKYT','TMDX','UAMY','USAR','UUUU','WWR',
    'ASTS','BKSY','FLY','GSAT','HEI','IRDM','KULR','LUNR','MNTS','PL',
    'RDW','RKLB','SATL','SATS','SIDU','SPIR','UFO','VOYG','VSAT',
    'SPY','QQQ','IWM'
]

TICKER_NAMES = {
    'AMD':'Advanced Micro Devices','AMPX':'Amprius Technologies','BABA':'Alibaba',
    'BIDU':'Baidu','BITF':'Bitfarms','CIFR':'Cipher Mining','CLSK':'CleanSpark',
    'CORZ':'Core Scientific','CRWV':'CoreWeave','EOSE':'Eos Energy','GOOGL':'Alphabet',
    'HUT':'Hut 8 Mining','IREN':'Iris Energy','LAES':'SEALSQ Corp','NBIS':'Nebius Group',
    'NUAI':'NuScale Power','NVDA':'NVIDIA','NVTS':'Navitas Semiconductor','PATH':'UiPath',
    'POWL':'Powell Industries','RR':'Rolls-Royce','SERV':'Serve Robotics','SNDK':'SanDisk',
    'TE':'Trane Technologies','TSLA':'Tesla','TSM':'TSMC','WDC':'Western Digital',
    'ZETA':'Zeta Global','AMAT':'Applied Materials','LRCX':'Lam Research',
    'MRAM':'Everspin Technologies','MRVL':'Marvell Technology','MU':'Micron Technology',
    'NTAP':'NetApp','PSTG':'Pure Storage','RMBS':'Rambus','SIMO':'Silicon Motion',
    'STX':'Seagate','AMTM':'Ametek','AVAV':'AeroVironment','BWXT':'BWX Technologies',
    'DPRO':'Draganfly','ESLT':'Elbit Systems','KRKNF':'Kraken Robotics',
    'KRMN':'Karman Holdings','KTOS':'Kratos Defense','LPTH':'LightPath Technologies',
    'MOB':'Mobilicom','MRCY':'Mercury Systems','ONDS':'OnDefense','OSS':'One Stop Systems',
    'PLTR':'Palantir','PRZO':'ParaZero','RCAT':'Red Cat Holdings','TDY':'Teledyne',
    'UMAC':'Unusual Machines','CRDO':'Credo Technology','IBRX':'ImmunityBio',
    'IONQ':'IonQ','IONR':'Ion Resources','LAC':'Lithium Americas','MP':'MP Materials',
    'NAK':'Northern Dynasty','NET':'Cloudflare','OPTT':'Ocean Power',
    'PPTA':'Perpetua Resources','RZLT':'Rezolve AI','SKYT':'SkyWater Tech',
    'TMDX':'TransMedics','UAMY':'US Antimony','USAR':'US Array','UUUU':'Energy Fuels',
    'WWR':'Westwater Resources','ASTS':'AST SpaceMobile','BKSY':'BlackSky',
    'FLY':'Fly Leasing','GSAT':'Globalstar','HEI':'Heico','IRDM':'Iridium',
    'KULR':'KULR Technology','LUNR':'Intuitive Machines','MNTS':'Momentus',
    'PL':'Planet Labs','RDW':'Redwire','RKLB':'Rocket Lab','SATL':'Satellogic',
    'SATS':'EchoStar','SIDU':'Sidus Space','SPIR':'Spire Global',
    'UFO':'Procure Space ETF','VOYG':'Voyager Digital','VSAT':'ViaSat',
    'SPY':'S&P 500 ETF','QQQ':'Nasdaq 100 ETF','IWM':'Russell 2000 ETF',
}

_cache = {'data': {}, 'ts': 0}
_lock = threading.Lock()
# Track API call count to stay under 60/min
_call_times = []
_call_lock = threading.Lock()


def rate_limit():
    """Ensure we stay under 60 calls/minute."""
    with _call_lock:
        now = time.time()
        # Remove calls older than 60s
        while _call_times and _call_times[0] < now - 60:
            _call_times.pop(0)
        if len(_call_times) >= 55:  # leave headroom
            sleep_for = 61 - (now - _call_times[0])
            if sleep_for > 0:
                print(f'  Rate limit pause: {sleep_for:.1f}s')
                time.sleep(sleep_for)
        _call_times.append(time.time())


def fetch_quote(symbol):
    """Fetch a single quote from Finnhub."""
    rate_limit()
    url = f'https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}'
    req = Request(url, headers={'User-Agent': 'ThemeTrack/1.0'})
    with urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode())
    # Finnhub quote: c=current, d=change, dp=change%, h=high, l=low, o=open, pc=prev close
    if not data.get('c'):
        return None
    return {
        'symbol': symbol,
        'name': TICKER_NAMES.get(symbol, symbol),
        'price': data.get('c'),
        'change': data.get('d'),
        'changePct': data.get('dp'),
        'volume': None,  # not in basic quote
        'high52': data.get('h'),  # today's high (52w needs premium)
        'low52': data.get('l'),   # today's low
        'mcap': None,
    }


def refresh_quotes():
    """Fetch all tickers. Finnhub free = 60 req/min, we have ~97 tickers."""
    all_data = {}
    total = len(ALL_TICKERS)
    errors = 0

    for i, sym in enumerate(ALL_TICKERS):
        try:
            q = fetch_quote(sym)
            if q:
                all_data[sym] = q
            if (i + 1) % 10 == 0:
                print(f'  [{i+1}/{total}] {len(all_data)} loaded, {errors} errors')
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f'  {sym}: {e}')

    with _lock:
        _cache['data'] = all_data
        _cache['ts'] = time.time()

    print(f'  Done — {len(all_data)}/{total} tickers cached ({errors} errors)')
    return all_data


def get_quotes():
    with _lock:
        age = time.time() - _cache['ts']
        if _cache['data'] and age < CACHE_TTL:
            return _cache['data'], True
        if _cache['data'] and age >= CACHE_TTL:
            # Return stale, refresh in background
            threading.Thread(target=refresh_quotes, daemon=True).start()
            return _cache['data'], True
    return refresh_quotes(), False


def background_refresh():
    time.sleep(CACHE_TTL)
    while True:
        try:
            print('Auto-refresh...')
            refresh_quotes()
        except Exception as e:
            print(f'Auto-refresh error: {e}')
        time.sleep(CACHE_TTL)


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        path = self.path.split('?')[0]

        if path == '/api/quotes':
            try:
                data, cached = get_quotes()
                body = json.dumps({
                    'quotes': data,
                    'cached': cached,
                    'ts': int(_cache['ts'] * 1000),
                    'count': len(data)
                }).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())
            return

        if path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return

        index_path = os.path.join(BASE_DIR, 'index.html')
        if not os.path.exists(index_path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'index.html not found - put it in the same folder as server.py')
            return

        with open(index_path, 'rb') as f:
            content = f.read()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt, *args):
        msg = args[0] if args else ''
        code = str(args[1]) if len(args) > 1 else ''
        if '/api/' in msg or code.startswith('4') or code.startswith('5'):
            print(f'  {msg} {code}')


class ReusableServer(HTTPServer):
    allow_reuse_address = True


if __name__ == '__main__':
    print(f'\n  ThemeTrack  |  {len(ALL_TICKERS)} tickers  |  Finnhub  |  port {PORT}')

    if not API_KEY:
        print('\n  ERROR: FINNHUB_API_KEY environment variable is not set.')
        print('  Set it in Railway: Settings -> Variables -> Add FINNHUB_API_KEY')
        exit(1)

    if not os.path.exists(os.path.join(BASE_DIR, 'index.html')):
        print(f'  WARNING: index.html not found in {BASE_DIR}')

    # Finnhub free tier: 60 req/min. 97 tickers = ~2 minutes to load fully.
    print(f'  Loading {len(ALL_TICKERS)} tickers (~2 min on free tier)...\n')
    threading.Thread(target=refresh_quotes, daemon=False).start()

    # Start background refresh after initial load completes
    threading.Thread(target=background_refresh, daemon=True).start()

    httpd = ReusableServer(('', PORT), Handler)
    print(f'  Open http://localhost:{PORT}  (prices appear as they load)\n')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('Stopped.')
