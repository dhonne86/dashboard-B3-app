import os
import base64
import csv
import hmac
import io
import json
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from flask import Flask, Response, jsonify, redirect, render_template_string, request, stream_with_context


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
GOOGLE_FINANCE_CSV_URL = os.environ.get("GOOGLE_FINANCE_CSV_URL", "")
GOOGLE_FINANCE_TIMEOUT = max(5, int(os.environ.get("GOOGLE_FINANCE_TIMEOUT", "12")))
DATABASE_PATH = os.environ.get("DATABASE_PATH", "dashboard_b3.sqlite3")
MARKET_REFRESH_SECONDS = max(15, int(os.environ.get("MARKET_REFRESH_SECONDS", "60")))
STREAM_HEARTBEAT_SECONDS = max(5, int(os.environ.get("STREAM_HEARTBEAT_SECONDS", "15")))
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
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
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


@app.route("/api/mercado/stream")
def mercado_stream():
    def event_stream():
        last_signature = None

        while True:
            payload = build_market_payload(use_cache=False)
            signature = payload.get("snapshot_id") or payload.get("atualizado_iso")
            if signature != last_signature:
                yield f"event: mercado\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                last_signature = signature
            else:
                heartbeat = {"status": "ok", "atualizado_iso": payload.get("atualizado_iso")}
                yield f"event: heartbeat\ndata: {json.dumps(heartbeat, ensure_ascii=False)}\n\n"

            time.sleep(STREAM_HEARTBEAT_SECONDS)

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/acoes")
def acoes():
    payload = build_market_payload()
    return jsonify([item for item in payload["ativos"] if item["tipo"] == "Acao B3"])


@app.route("/api/indices")
def indices():
    payload = build_market_payload()
    return jsonify([item for item in payload["ativos"] if item["tipo"] == "Indice"])


@app.route("/api/snapshots")
def snapshots():
    limit = min(max(int(request.args.get("limit", "20")), 1), 100)
    return jsonify(fetch_market_snapshots(limit))


def build_market_payload(use_cache=True):
    ensure_database()
    if use_cache:
        cached = load_cached_market_payload(MARKET_REFRESH_SECONDS)
        if cached:
            return cached

    end = datetime.now()
    assets = fetch_google_finance_assets()

    if not assets:
        assets = fetch_brapi_assets()

    if not assets:
        assets = build_sample_assets()

    enrich_assets_with_agents(assets)

    winners = sorted(assets, key=lambda item: item["variacao"], reverse=True)
    signal_summary = summarize_entry_signals(assets)

    payload = {
        "atualizado_em": end.strftime("%d/%m/%Y %H:%M"),
        "atualizado_iso": end.isoformat(timespec="seconds"),
        "fonte": market_source_label(assets),
        "mercado": "B3",
        "tempo_real": {
            "ativo": True,
            "modo": "SSE",
            "intervalo_refresh_segundos": MARKET_REFRESH_SECONDS,
            "intervalo_stream_segundos": STREAM_HEARTBEAT_SECONDS,
            "observacao": "Cotas publicas da B3 podem ter atraso; APIs oficiais em tempo real exigem contratacao B2B.",
        },
        "banco": {
            "tipo": "sqlite",
            "arquivo": DATABASE_PATH,
        },
        "agentes": {
            "analise_mercado": "ativo",
            "sinais_entrada": "ativo",
            "extracao_b3": "monitorado",
            "google_finance_model": "ativo" if any(item["fonte"] == "google_finance" for item in assets) else "fallback",
            "validade_sinal": "proximo_pregao",
        },
        "resumo": {
            "ativos": len(assets),
            "alta": winners[0]["ticker"],
            "baixa": winners[-1]["ticker"],
            "media": round(sum(item["variacao"] for item in assets) / len(assets), 2),
            "sinais": signal_summary,
        },
        "ativos": assets,
    }

    payload["snapshot_id"] = save_market_payload(payload)
    return payload


def ensure_database():
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS market_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS asset_quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                created_at TEXT NOT NULL,
                price REAL NOT NULL,
                variation REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                volume INTEGER NOT NULL,
                source TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY(snapshot_id) REFERENCES market_snapshots(id)
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_market_snapshots_created ON market_snapshots(created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_asset_quotes_ticker_created ON asset_quotes(ticker, created_at)")


def load_cached_market_payload(max_age_seconds):
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT id, created_at, payload_json FROM market_snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()

    if not row:
        return None

    created_at = datetime.fromisoformat(row["created_at"])
    age_seconds = (datetime.now() - created_at).total_seconds()
    if age_seconds > max_age_seconds:
        return None

    payload = json.loads(row["payload_json"])
    payload["snapshot_id"] = row["id"]
    payload["cache"] = {"ativo": True, "idade_segundos": round(age_seconds)}
    return payload


def save_market_payload(payload):
    created_at = payload["atualizado_iso"]
    payload_to_store = dict(payload)
    payload_to_store.pop("snapshot_id", None)
    payload_json = json.dumps(payload_to_store, ensure_ascii=False)

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.execute(
            "INSERT INTO market_snapshots (created_at, source, payload_json) VALUES (?, ?, ?)",
            (created_at, payload["fonte"], payload_json),
        )
        snapshot_id = cursor.lastrowid
        connection.executemany(
            """
            INSERT INTO asset_quotes (
                snapshot_id, ticker, created_at, price, variation, high, low, volume, source, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    snapshot_id,
                    asset["ticker"],
                    created_at,
                    asset["preco"],
                    asset["variacao"],
                    asset["maxima"],
                    asset["minima"],
                    asset["volume"],
                    asset["fonte"],
                    json.dumps(asset, ensure_ascii=False),
                )
                for asset in payload["ativos"]
            ],
        )

    return snapshot_id


def fetch_market_snapshots(limit):
    ensure_database()
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, created_at, source, payload_json
            FROM market_snapshots
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    snapshots = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        snapshots.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "source": row["source"],
                "resumo": payload.get("resumo", {}),
            }
        )
    return snapshots


def market_source_label(assets):
    if any(item["fonte"] == "google_finance" for item in assets):
        return "Google Sheets / GOOGLEFINANCE"
    if any(item["fonte"] == "brapi" for item in assets):
        return "brapi.dev"
    return "dados locais"


def enrich_assets_with_agents(assets):
    for asset in assets:
        analysis = market_analysis_agent(asset)
        asset["analise"] = analysis
        asset["sinal_entrada"] = entry_signal_agent(asset, analysis)


def market_analysis_agent(asset):
    points = asset["historico"]
    closes = [point["close"] for point in points if point.get("close")]
    highs = [point["high"] for point in points if point.get("high")]
    lows = [point["low"] for point in points if point.get("low")]
    volumes = [point["volume"] for point in points if point.get("volume") is not None]
    last = closes[-1] if closes else asset["preco"]
    short_window = min(5, len(closes)) if closes else 1
    long_window = min(20, len(closes)) if closes else 1
    short_avg = average(closes[-short_window:]) if closes else last
    long_avg = average(closes[-long_window:]) if closes else last
    long_first = closes[-long_window] if closes else last
    slope = pct_change(long_first, last)
    period_return = pct_change(closes[0], last) if closes else 0
    short_return = pct_change(closes[-min(3, len(closes))], last) if len(closes) > 1 else 0
    up_days = count_up_days(closes[-6:])
    max_price = max(highs) if highs else asset["maxima"]
    min_price = min(lows) if lows else asset["minima"]
    price_range = max(max_price - min_price, 0.01)
    range_position = ((last - min_price) / price_range) * 100
    avg_volume = average(volumes) if volumes else max(asset["volume"], 1)
    volume_relative = asset["volume"] / avg_volume if avg_volume else 1
    volatility = average(
        [((point["high"] - point["low"]) / point["close"]) * 100 for point in points if point.get("close")]
    )
    amplitude = ((max_price - min_price) / last) * 100 if last else 0
    support = min(lows[-10:]) if lows else min_price
    resistance = max(highs[-10:]) if highs else max_price

    if last > short_avg and short_avg > long_avg:
        trend = "alta"
    elif last < short_avg and short_avg < long_avg:
        trend = "baixa"
    else:
        trend = "lateral"

    if range_position >= 70 and asset["variacao"] > 1 and volume_relative >= 1.1:
        strength = "forte"
    elif range_position < 35 or asset["variacao"] < -1 or volume_relative < 0.7:
        strength = "fraca"
    else:
        strength = "moderada"

    if short_return > 0 and period_return > 0 and up_days >= 3:
        momentum = "acelerando"
    elif period_return > 0 and short_return < -1.5:
        momentum = "reversao_baixa"
    elif period_return > 0 and short_return < 0:
        momentum = "perdendo_forca"
    elif period_return < 0 and short_return > 0:
        momentum = "reversao_alta"
    else:
        momentum = "neutro"

    if volatility > 3.5 or amplitude > 12 or (trend == "baixa" and strength == "fraca"):
        risk = "alto"
    elif volatility < 1.5 and trend in ("alta", "lateral") and range_position >= 50:
        risk = "baixo"
    else:
        risk = "medio"

    score = min(
        100,
        trend_score(trend) + strength_score(strength) + momentum_score(momentum) + risk_score(risk),
    )

    return {
        "agente": "analise_mercado",
        "tendencia": trend,
        "forca": strength,
        "momentum": momentum,
        "risco": risk,
        "score": round(score),
        "vies": trend.upper() if trend != "lateral" else "NEUTRO",
        "suporte": round(support, 2),
        "resistencia": round(resistance, 2),
        "detalhes": {
            "media_curta": round(short_avg, 2),
            "media_longa": round(long_avg, 2),
            "inclinacao_pct": round(slope, 2),
            "retorno_periodo_pct": round(period_return, 2),
            "retorno_curto_pct": round(short_return, 2),
            "posicao_range_pct": round(range_position, 2),
            "volume_relativo": round(volume_relative, 2),
            "volatilidade_pct": round(volatility, 2),
            "dias_alta": up_days,
            "qualidade_dados": round(min(100, (len(points) / 20) * 100)),
        },
    }


def entry_signal_agent(asset, analysis):
    price = asset["preco"]
    support = analysis["suporte"]
    resistance = analysis["resistencia"]
    volatility_pct = analysis["detalhes"]["volatilidade_pct"]
    quality = analysis["detalhes"]["qualidade_dados"]
    volume_relative = analysis["detalhes"]["volume_relativo"]
    volume_score = 100 if volume_relative >= 1.2 else 70 if volume_relative >= 1 else 40

    if quality < 60 or price <= 0 or support <= 0 or resistance <= 0 or support >= resistance:
        return hold_signal("Dados insuficientes para sinal operacional.", quality, volume_score)

    buy_stop = min(support * 0.995, price * (1 - max(0.008, (volatility_pct / 100) * 0.60)))
    buy_target = min(price + ((price - buy_stop) * 1.8), resistance * 1.01)
    buy_rr = risk_reward(price, buy_stop, buy_target, "COMPRA")

    sell_stop = max(resistance * 1.005, price * (1 + max(0.008, (volatility_pct / 100) * 0.60)))
    sell_target = max(price - ((sell_stop - price) * 1.8), support * 0.99)
    sell_rr = risk_reward(price, sell_stop, sell_target, "VENDA")

    confidence = calculate_signal_confidence(analysis, max(buy_rr, sell_rr), volume_score)

    buy_conditions = (
        analysis["vies"] == "ALTA"
        and analysis["score"] >= 60
        and analysis["momentum"] in ("acelerando", "reversao_alta")
        and support < price < resistance
        and buy_rr >= 1.5
        and confidence >= 65
        and analysis["risco"] != "alto"
    )
    sell_conditions = (
        analysis["vies"] == "BAIXA"
        and analysis["score"] >= 60
        and analysis["momentum"] in ("reversao_baixa", "perdendo_forca")
        and support < price < resistance
        and sell_rr >= 1.5
        and confidence >= 65
    )

    if buy_conditions:
        return {
            "agente": "sinais_entrada",
            "sinal": "COMPRA",
            "preco_entrada": round(price, 2),
            "stop": round(buy_stop, 2),
            "alvo": round(buy_target, 2),
            "risco_retorno": round(buy_rr, 2),
            "confianca": confidence,
            "validade": "proximo_pregao",
            "justificativa_curta": "Vies de alta com momentum favoravel e risco-retorno minimo atendido.",
        }

    if sell_conditions:
        return {
            "agente": "sinais_entrada",
            "sinal": "VENDA",
            "preco_entrada": round(price, 2),
            "stop": round(sell_stop, 2),
            "alvo": round(sell_target, 2),
            "risco_retorno": round(sell_rr, 2),
            "confianca": confidence,
            "validade": "proximo_pregao",
            "justificativa_curta": "Vies de baixa com perda de momentum e risco-retorno minimo atendido.",
        }

    return hold_signal("Sem alinhamento suficiente entre tendencia, momentum e risco-retorno.", quality, volume_score)


def hold_signal(reason, quality, volume_score):
    confidence = round(min(100, (0.55 * quality) + (0.45 * volume_score)))
    return {
        "agente": "sinais_entrada",
        "sinal": "AGUARDAR",
        "preco_entrada": None,
        "stop": None,
        "alvo": None,
        "risco_retorno": None,
        "confianca": confidence,
        "validade": "proximo_pregao",
        "justificativa_curta": reason,
    }


def summarize_entry_signals(assets):
    summary = {"COMPRA": 0, "VENDA": 0, "AGUARDAR": 0}
    for asset in assets:
        signal = asset.get("sinal_entrada", {}).get("sinal", "AGUARDAR")
        summary[signal] = summary.get(signal, 0) + 1
    return summary


def average(values):
    valid = [value for value in values if value is not None]
    return sum(valid) / len(valid) if valid else 0


def pct_change(start, end):
    return ((end - start) / start) * 100 if start else 0


def count_up_days(closes):
    return sum(1 for index in range(1, len(closes)) if closes[index] > closes[index - 1])


def risk_reward(entry, stop, target, signal):
    if signal == "COMPRA":
        risk = entry - stop
        reward = target - entry
    else:
        risk = stop - entry
        reward = entry - target
    return reward / risk if risk > 0 and reward > 0 else 0


def calculate_signal_confidence(analysis, rr, volume_score):
    momentum_value = {
        "acelerando": 80,
        "reversao_alta": 65,
        "neutro": 45,
        "perdendo_forca": 55,
        "reversao_baixa": 70,
    }.get(analysis["momentum"], 45)
    quality = analysis["detalhes"]["qualidade_dados"]
    confidence = (
        0.35 * analysis["score"]
        + 0.25 * momentum_value
        + 0.20 * quality
        + 0.10 * min(rr / 2, 1) * 100
        + 0.10 * volume_score
    )
    return round(min(100, confidence))


def trend_score(trend):
    return {"alta": 30, "baixa": 30, "lateral": 15}.get(trend, 0)


def strength_score(strength):
    return {"forte": 25, "moderada": 12, "fraca": 0}.get(strength, 0)


def momentum_score(momentum):
    return {
        "acelerando": 25,
        "reversao_alta": 18,
        "neutro": 10,
        "perdendo_forca": 18,
        "reversao_baixa": 25,
    }.get(momentum, 0)


def risk_score(risk):
    return {"baixo": 20, "medio": 10, "alto": 0}.get(risk, 0)


def fetch_google_finance_assets():
    if not GOOGLE_FINANCE_CSV_URL:
        return []

    request = urllib.request.Request(
        GOOGLE_FINANCE_CSV_URL,
        headers={
            "Accept": "text/csv,text/plain,*/*",
            "User-Agent": "Dashboard-B3-GoogleFinance/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=GOOGLE_FINANCE_TIMEOUT) as response:
            content = response.read().decode("utf-8-sig")
    except Exception:
        return []

    rows = list(csv.DictReader(io.StringIO(content)))
    if not rows:
        return []

    grouped = {}
    for row in rows:
        normalized = {normalize_key(key): value for key, value in row.items() if key}
        ticker = clean_ticker(normalized.get("ticker") or normalized.get("ativo") or normalized.get("symbol"))
        if ticker not in B3_TICKERS:
            continue

        point = google_finance_point(normalized)
        if point:
            grouped.setdefault(ticker, {"rows": [], "name": None}).get("rows").append(point)

        name = normalized.get("nome") or normalized.get("name") or normalized.get("empresa")
        if name:
            grouped.setdefault(ticker, {"rows": [], "name": None})["name"] = name.strip()

        price = parse_float(normalized.get("preco") or normalized.get("price") or normalized.get("close") or normalized.get("fechamento"))
        if price is not None and not point:
            grouped.setdefault(ticker, {"rows": [], "name": None})["rows"].append(
                google_finance_point_from_quote(normalized, price)
            )

    assets = []
    for ticker, bundle in grouped.items():
        points = sorted(bundle["rows"], key=lambda item: item["date_iso"])
        if not points:
            continue

        points = points[-30:]
        first = points[0]["close"]
        last = points[-1]["close"]
        latest = points[-1]
        variation = parse_float(latest.get("variation"))
        if variation is None:
            variation = ((last - first) / first) * 100 if first else 0

        assets.append(
            {
                "ticker": ticker,
                "nome": bundle["name"] or B3_TICKERS[ticker],
                "tipo": "Acao B3",
                "preco": round(last, 2),
                "variacao": round(variation, 2),
                "maxima": round(max(point["high"] for point in points), 2),
                "minima": round(min(point["low"] for point in points), 2),
                "volume": int(latest.get("volume") or 0),
                "historico": points,
                "fonte": "google_finance",
            }
        )

    return assets


def google_finance_point(row):
    close = parse_float(row.get("close") or row.get("fechamento") or row.get("preco") or row.get("price"))
    if close is None:
        return None

    date = parse_sheet_date(row.get("date") or row.get("data") or row.get("dia"))
    open_price = parse_float(row.get("open") or row.get("abertura")) or close
    high = parse_float(row.get("high") or row.get("maxima") or row.get("max")) or max(open_price, close)
    low = parse_float(row.get("low") or row.get("minima") or row.get("min")) or min(open_price, close)
    volume = parse_int(row.get("volume")) or 0

    return {
        "date": date.strftime("%d/%m"),
        "date_iso": date.date().isoformat(),
        "open": round(open_price, 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "close": round(close, 2),
        "volume": volume,
        "variation": parse_float(row.get("variacao") or row.get("change") or row.get("change_pct")),
    }


def google_finance_point_from_quote(row, price):
    date = parse_sheet_date(row.get("date") or row.get("data") or row.get("dia"))
    high = parse_float(row.get("maxima") or row.get("high")) or price
    low = parse_float(row.get("minima") or row.get("low")) or price
    return {
        "date": date.strftime("%d/%m"),
        "date_iso": date.date().isoformat(),
        "open": price,
        "high": round(high, 2),
        "low": round(low, 2),
        "close": price,
        "volume": parse_int(row.get("volume")) or 0,
        "variation": parse_float(row.get("variacao") or row.get("change") or row.get("change_pct")),
    }


def normalize_key(key):
    key = key.strip().lower()
    replacements = {
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }
    for old, new in replacements.items():
        key = key.replace(old, new)
    return key.replace(" ", "_").replace("%", "pct")


def clean_ticker(value):
    if not value:
        return ""
    return str(value).strip().upper().replace("BVMF:", "").replace("B3:", "").replace(".SA", "")


def parse_float(value):
    if value is None or value == "":
        return None
    text = str(value).strip().replace("%", "").replace("R$", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value):
    number = parse_float(value)
    return int(number) if number is not None else None


def parse_sheet_date(value):
    if not value:
        return datetime.now()

    text = str(value).strip()
    formats = ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y", "%Y/%m/%d")
    for date_format in formats:
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            pass

    try:
        serial = float(text)
        return datetime(1899, 12, 30) + timedelta(days=serial)
    except ValueError:
        return datetime.now()


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
                "date_iso": date.date().isoformat(),
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
                "date_iso": date.date().isoformat(),
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
