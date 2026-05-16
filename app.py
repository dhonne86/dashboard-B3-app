import os
import base64
import hmac
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from flask import Flask, Response, jsonify, redirect, render_template_string, request


app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


def load_env_file(path=".env"):
    if not os.path.exists(path):
        return

    with open(path, encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()

BRAPI_TOKEN = os.environ.get("BRAPI_TOKEN", "")
BRAPI_URL = "https://brapi.dev/api/quote/{tickers}"
DASHBOARD_USER = os.environ.get("DASHBOARD_USER", "admin")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")
AUTH_REALM = "Dashboard B3"

B3_TICKERS = {
    "PETR4": "Petrobras PN",
    "VALE3": "Vale ON",
    "ITUB4": "Itau Unibanco PN",
    "BBDC4": "Bradesco PN",
    "ABEV3": "Ambev ON",
    "WEGE3": "WEG ON",
    "BBAS3": "Banco do Brasil ON",
    "B3SA3": "B3 ON",
}

SAMPLE_PRICES = {
    "PETR4": [37.82, 38.14, 38.02, 38.66, 39.21, 39.04, 39.58],
    "VALE3": [61.25, 60.88, 61.74, 62.10, 61.92, 62.44, 63.18],
    "ITUB4": [32.18, 32.41, 32.62, 32.55, 33.02, 33.26, 33.44],
    "BBDC4": [13.48, 13.56, 13.71, 13.68, 13.84, 13.90, 14.02],
    "ABEV3": [12.06, 12.10, 12.18, 12.15, 12.24, 12.27, 12.36],
    "WEGE3": [39.64, 40.12, 40.48, 40.36, 41.22, 41.80, 42.18],
    "BBAS3": [27.80, 28.02, 28.16, 28.40, 28.34, 28.62, 28.88],
    "B3SA3": [12.38, 12.44, 12.52, 12.49, 12.63, 12.72, 12.86],
}


@app.before_request
def require_authentication():
    if request.path == "/healthz":
        return None

    if not DASHBOARD_PASSWORD:
        return None

    if is_authorized(request.headers.get("Authorization", "")):
        return None

    return Response(
        "Autenticacao obrigatoria.",
        401,
        {"WWW-Authenticate": f'Basic realm="{AUTH_REALM}", charset="UTF-8"'},
    )


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self'; "
        "connect-src 'self'; "
        "img-src 'self' data:; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )
    return response


def is_authorized(auth_header):
    if not auth_header.startswith("Basic "):
        return False

    try:
        encoded = auth_header.split(" ", 1)[1]
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, password = decoded.split(":", 1)
    except Exception:
        return False

    return hmac.compare_digest(username, DASHBOARD_USER) and hmac.compare_digest(password, DASHBOARD_PASSWORD)


@app.route("/")
def index():
    with open("index.html", encoding="utf-8") as page:
        return render_template_string(page.read())


@app.route("/mobile")
def mobile():
    with open("dashboard_mobile.html", encoding="utf-8") as page:
        return render_template_string(page.read())


@app.route("/iphone")
def iphone():
    return redirect("/mobile")


@app.route("/styles.css")
def styles():
    with open("styles.css", encoding="utf-8") as stylesheet:
        return stylesheet.read(), 200, {"Content-Type": "text/css; charset=utf-8"}


@app.route("/styles_mobile.css")
def styles_mobile():
    with open("styles_mobile.css", encoding="utf-8") as stylesheet:
        return stylesheet.read(), 200, {"Content-Type": "text/css; charset=utf-8"}


@app.route("/manifest.webmanifest")
def manifest():
    return jsonify(
        {
            "name": "Dashboard Financeiro",
            "short_name": "Dashboard",
            "start_url": "/mobile",
            "display": "standalone",
            "background_color": "#eef2f5",
            "theme_color": "#10b981",
        }
    )


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok", "mercado": "B3"})


@app.route("/api/mercado")
def mercado():
    return jsonify(build_market_payload())


@app.route("/api/acoes")
def acoes():
    payload = build_market_payload()
    return jsonify([item for item in payload["ativos"] if item["tipo"] == "Acao B3"])


@app.route("/api/indices")
def indices():
    payload = build_market_payload()
    return jsonify([item for item in payload["ativos"] if item["tipo"] == "Indice"])


def build_market_payload():
    end = datetime.today()
    assets = fetch_brapi_assets()

    if not assets:
        assets = build_sample_assets()

    winners = sorted(assets, key=lambda item: item["variacao"], reverse=True)

    return {
        "atualizado_em": end.strftime("%d/%m/%Y %H:%M"),
        "fonte": "brapi.dev" if any(item["fonte"] == "brapi" for item in assets) else "dados locais",
        "mercado": "B3",
        "resumo": {
            "ativos": len(assets),
            "alta": winners[0]["ticker"],
            "baixa": winners[-1]["ticker"],
            "media": round(sum(item["variacao"] for item in assets) / len(assets), 2),
        },
        "ativos": assets,
    }


def fetch_brapi_assets():
    if not BRAPI_TOKEN:
        return []

    assets = []

    for ticker in B3_TICKERS:
        item = fetch_brapi_quote(ticker)
        if not item:
            continue

        ticker = item.get("symbol")
        if ticker not in B3_TICKERS:
            continue

        points = brapi_points(item.get("historicalDataPrice", []), ticker)
        if not points:
            points = sample_points(ticker)

        first = points[0]["close"]
        last = points[-1]["close"]
        variation = item.get("regularMarketChangePercent")
        if variation is None:
            variation = ((last - first) / first) * 100 if first else 0

        assets.append(
            {
                "ticker": ticker,
                "nome": item.get("longName") or item.get("shortName") or B3_TICKERS[ticker],
                "tipo": "Acao B3",
                "preco": round(float(item.get("regularMarketPrice") or last), 2),
                "variacao": round(variation, 2),
                "maxima": round(max(point["high"] for point in points), 2),
                "minima": round(min(point["low"] for point in points), 2),
                "volume": int(item.get("regularMarketVolume") or points[-1]["volume"]),
                "historico": points,
                "fonte": "brapi",
            }
        )

    return assets


def fetch_brapi_quote(ticker):
    params = urllib.parse.urlencode(
        {
            "range": "3mo",
            "interval": "1d",
            "token": BRAPI_TOKEN,
        }
    )
    url = f"{BRAPI_URL.format(tickers=ticker)}?{params}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {BRAPI_TOKEN}",
            "User-Agent": "Dashboard-B3/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json_loads(response.read().decode("utf-8"))
    except Exception:
        return None

    results = payload.get("results", [])
    return results[0] if results else None


def brapi_points(history, ticker):
    points = []

    for item in history:
        close = item.get("close") or item.get("adjClose")
        if close is None:
            continue

        date = datetime.fromtimestamp(item["date"]) if isinstance(item.get("date"), int) else datetime.today()
        points.append(
            {
                "date": date.strftime("%d/%m"),
                "open": round(float(item.get("open") or close), 2),
                "high": round(float(item.get("high") or close), 2),
                "low": round(float(item.get("low") or close), 2),
                "close": round(float(close), 2),
                "volume": int(item.get("volume") or 0),
            }
        )

    return points[-30:]


def build_sample_assets():
    assets = []

    for ticker, name in B3_TICKERS.items():
        points = sample_points(ticker)
        first = points[0]["close"]
        last = points[-1]["close"]
        variation = ((last - first) / first) * 100 if first else 0

        assets.append(
            {
                "ticker": ticker,
                "nome": name,
                "tipo": "Acao B3",
                "preco": round(last, 2),
                "variacao": round(variation, 2),
                "maxima": round(max(point["high"] for point in points), 2),
                "minima": round(min(point["low"] for point in points), 2),
                "volume": int(points[-1]["volume"]),
                "historico": points,
                "fonte": "local",
            }
        )

    return assets


def json_loads(content):
    import json
    return json.loads(content)


def sample_points(ticker):
    today = datetime.today()
    prices = SAMPLE_PRICES[ticker]
    points = []

    for index, price in enumerate(prices):
        date = today - timedelta(days=len(prices) - index - 1)
        points.append(
            {
                "date": date.strftime("%d/%m"),
                "open": round(price * 0.992, 2),
                "high": round(price * 1.012, 2),
                "low": round(price * 0.984, 2),
                "close": round(price, 2),
                "volume": 1250000 + index * 84000,
            }
        )

    return points


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("DEBUG", "1") == "1",
    )
