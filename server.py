#!/usr/bin/env python3
"""ZYCRYPTO PLATFORM v1.3 — SQLite (sync) + GitHub backup + Multi-crypto"""
import json, os, sqlite3, hashlib, secrets, time, threading, requests, base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ══════════════════════════════════════════════════════════════
#   CONFIG
# ══════════════════════════════════════════════════════════════
PORT        = int(os.environ.get("PORT", 8000))
SECRET_KEY  = os.environ.get("SECRET_KEY", "zyproz-zycrypto-2026-xK9mP2qR")
TG_TOKEN    = os.environ.get("TG_TOKEN",  "8858889412:AAElLpyQCIqw3PIYeAJtxeH56DQgXBUn6Ls")
TG_ADMIN_ID = int(os.environ.get("TG_ADMIN", "5354522228"))
TG_GROUP_ID  = os.environ.get("TG_GROUP_ID", "")
BOT_COOLDOWN = int(os.environ.get("BOT_COOLDOWN", "300"))
# ── MetaAPI — Vantage Markets (vrai argent) ────────────────────
META_TOKEN   = os.environ.get("META_TOKEN",   "")
META_ACCOUNT = os.environ.get("META_ACCOUNT", "c2ee22ce-f12a-4168-afba-57b749eb30c3")
META_REGION  = os.environ.get("META_REGION",  "new-york")  # new-york|london|singapore
REAL_TRADING = os.environ.get("REAL_TRADING", "0") == "1"  # 0=DEMO, 1=RÉELam (optionnel)
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "ugo.scule@gmail.com").lower()
GH_TOKEN    = os.environ.get("GH_TOKEN",  "")
DB_REPO     = os.environ.get("DB_REPO",   "zycrypto-db")
DB_OWNER    = os.environ.get("DB_OWNER",  "")
DB_PATH     = "/tmp/zycrypto.db"

# ── Symboles ──────────────────────────────────────────────────
SYMBOLS = {
    # ── CRYPTO (Binance) ────────────────────────────────────────
    "BTC":    {"name":"Bitcoin",      "icon":"₿",   "type":"CRYPTO","src":"binance","pair":"BTCUSDT",   "color":"#f5c518"},
    "ETH":    {"name":"Ethereum",     "icon":"Ξ",   "type":"CRYPTO","src":"binance","pair":"ETHUSDT",   "color":"#627eea"},
    "BNB":    {"name":"BNB",          "icon":"◈",   "type":"CRYPTO","src":"binance","pair":"BNBUSDT",   "color":"#f3ba2f"},
    "SOL":    {"name":"Solana",       "icon":"◎",   "type":"CRYPTO","src":"binance","pair":"SOLUSDT",   "color":"#9945ff"},
    "XRP":    {"name":"Ripple",       "icon":"✕",   "type":"CRYPTO","src":"binance","pair":"XRPUSDT",   "color":"#00aae4"},
    "DOGE":   {"name":"Dogecoin",     "icon":"Ð",   "type":"CRYPTO","src":"binance","pair":"DOGEUSDT",  "color":"#c2a633"},
    "ADA":    {"name":"Cardano",      "icon":"₳",   "type":"CRYPTO","src":"binance","pair":"ADAUSDT",   "color":"#0033ad"},
    "LTC":    {"name":"Litecoin",     "icon":"Ł",   "type":"CRYPTO","src":"binance","pair":"LTCUSDT",   "color":"#bfbbbb"},
    "DOT":    {"name":"Polkadot",     "icon":"●",   "type":"CRYPTO","src":"binance","pair":"DOTUSDT",   "color":"#e6007a"},
    "LINK":   {"name":"Chainlink",    "icon":"⬡",   "type":"CRYPTO","src":"binance","pair":"LINKUSDT",  "color":"#2a5ada"},
    "AVAX":   {"name":"Avalanche",    "icon":"🔺",  "type":"CRYPTO","src":"binance","pair":"AVAXUSDT",  "color":"#e84142"},
    "MATIC":  {"name":"Polygon",      "icon":"⬟",   "type":"CRYPTO","src":"binance","pair":"MATICUSDT", "color":"#8247e5"},
    "UNI":    {"name":"Uniswap",      "icon":"🦄",  "type":"CRYPTO","src":"binance","pair":"UNIUSDT",   "color":"#ff007a"},
    "ATOM":   {"name":"Cosmos",       "icon":"⚛",   "type":"CRYPTO","src":"binance","pair":"ATOMUSDT",  "color":"#2e3148"},
    "NEAR":   {"name":"NEAR",         "icon":"Ν",   "type":"CRYPTO","src":"binance","pair":"NEARUSDT",  "color":"#00c08b"},
    # ── MÉTAUX (Yahoo Finance) ──────────────────────────────────
    "GOLD":   {"name":"Or",           "icon":"🥇",  "type":"METAL", "src":"yahoo",  "pair":"XAUUSD=X",  "color":"#ffd700"},
    "SILVER": {"name":"Argent",       "icon":"🥈",  "type":"METAL", "src":"yahoo",  "pair":"XAGUSD=X",  "color":"#c0c0c0"},
    "PLAT":   {"name":"Platine",      "icon":"💿",  "type":"METAL", "src":"yahoo",  "pair":"XPTUSD=X",  "color":"#e5e4e2"},
    "COPPER": {"name":"Cuivre",       "icon":"🔶",  "type":"METAL", "src":"yahoo",  "pair":"HG=F",       "color":"#b87333"},
    # ── FOREX MAJEURS (Yahoo Finance) ───────────────────────────
    "EURUSD": {"name":"EUR/USD",      "icon":"€$",  "type":"FOREX", "src":"yahoo",  "pair":"EURUSD=X",  "color":"#003399"},
    "GBPUSD": {"name":"GBP/USD",      "icon":"£$",  "type":"FOREX", "src":"yahoo",  "pair":"GBPUSD=X",  "color":"#012169"},
    "USDJPY": {"name":"USD/JPY",      "icon":"$¥",  "type":"FOREX", "src":"yahoo",  "pair":"USDJPY=X",  "color":"#bc002d"},
    "USDCHF": {"name":"USD/CHF",      "icon":"$Fr", "type":"FOREX", "src":"yahoo",  "pair":"USDCHF=X",  "color":"#ff0000"},
    "AUDUSD": {"name":"AUD/USD",      "icon":"A$",  "type":"FOREX", "src":"yahoo",  "pair":"AUDUSD=X",  "color":"#00843d"},
    "USDCAD": {"name":"USD/CAD",      "icon":"C$",  "type":"FOREX", "src":"yahoo",  "pair":"USDCAD=X",  "color":"#ff0000"},
    "NZDUSD": {"name":"NZD/USD",      "icon":"NZ$", "type":"FOREX", "src":"yahoo",  "pair":"NZDUSD=X",  "color":"#00247d"},
    "EURGBP": {"name":"EUR/GBP",      "icon":"€£",  "type":"FOREX", "src":"yahoo",  "pair":"EURGBP=X",  "color":"#003399"},
    "EURJPY": {"name":"EUR/JPY",      "icon":"€¥",  "type":"FOREX", "src":"yahoo",  "pair":"EURJPY=X",  "color":"#003399"},
    "GBPJPY": {"name":"GBP/JPY",      "icon":"£¥",  "type":"FOREX", "src":"yahoo",  "pair":"GBPJPY=X",  "color":"#012169"},
    # ── INDICES (Yahoo Finance) ──────────────────────────────────
    "US500":  {"name":"S&P 500",      "icon":"📊",  "type":"INDEX", "src":"yahoo",  "pair":"^GSPC",      "color":"#1a56db"},
    "US100":  {"name":"NASDAQ 100",   "icon":"💻",  "type":"INDEX", "src":"yahoo",  "pair":"^NDX",       "color":"#7e3af2"},
    "US30":   {"name":"Dow Jones",    "icon":"🏛",  "type":"INDEX", "src":"yahoo",  "pair":"^DJI",       "color":"#1c64f2"},
    "DE40":   {"name":"DAX",          "icon":"🇩🇪", "type":"INDEX", "src":"yahoo",  "pair":"^GDAXI",     "color":"#000000"},
    "UK100":  {"name":"FTSE 100",     "icon":"🇬🇧", "type":"INDEX", "src":"yahoo",  "pair":"^FTSE",      "color":"#012169"},
    "JP225":  {"name":"Nikkei 225",   "icon":"🗻",  "type":"INDEX", "src":"yahoo",  "pair":"^N225",      "color":"#bc002d"},
    "FR40":   {"name":"CAC 40",       "icon":"🇫🇷", "type":"INDEX", "src":"yahoo",  "pair":"^FCHI",      "color":"#0055a4"},
    # ── ETF (Yahoo Finance) ──────────────────────────────────────
    "SPY":    {"name":"S&P 500 ETF",  "icon":"🕵",  "type":"ETF",   "src":"yahoo",  "pair":"SPY",        "color":"#1a56db"},
    "QQQ":    {"name":"NASDAQ ETF",   "icon":"📱",  "type":"ETF",   "src":"yahoo",  "pair":"QQQ",        "color":"#7e3af2"},
    "GLD":    {"name":"Gold ETF",     "icon":"🏅",  "type":"ETF",   "src":"yahoo",  "pair":"GLD",        "color":"#ffd700"},
    # ── MATIÈRES PREMIÈRES (Yahoo Finance) ──────────────────────
    "OIL":    {"name":"Pétrole WTI",  "icon":"🛢",  "type":"COMM",  "src":"yahoo",  "pair":"CL=F",       "color":"#1e1e1e"},
    "BRENT":  {"name":"Pétrole Brent","icon":"⛽",  "type":"COMM",  "src":"yahoo",  "pair":"BZ=F",       "color":"#333333"},
    "NATGAS": {"name":"Gaz Naturel",  "icon":"🔥",  "type":"COMM",  "src":"yahoo",  "pair":"NG=F",       "color":"#ff6b35"},
    "WHEAT":  {"name":"Blé",          "icon":"🌾",  "type":"COMM",  "src":"yahoo",  "pair":"ZW=F",       "color":"#d4a017"},
    "CORN":   {"name":"Maïs",         "icon":"🌽",  "type":"COMM",  "src":"yahoo",  "pair":"ZC=F",       "color":"#f5c518"},
    "COFFEE": {"name":"Café",         "icon":"☕",  "type":"COMM",  "src":"yahoo",  "pair":"KC=F",       "color":"#4a2c2a"},
}

# ══════════════════════════════════════════════════════════════
#   SQLITE — Base de données synchrone
# ══════════════════════════════════════════════════════════════
def get_db():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        username TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        token TEXT,
        balance REAL DEFAULT 1000.0,
        levier INTEGER DEFAULT 200,
        mise REAL DEFAULT 10.0,
        tp REAL DEFAULT 2.0,
        sl REAL DEFAULT 2.0,
        interval INTEGER DEFAULT 5,
        bot_actif INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        meta_token TEXT DEFAULT '',
        account_id TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS positions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,
        entry REAL NOT NULL,
        volume REAL NOT NULL,
        tp REAL NOT NULL,
        sl REAL NOT NULL,
        marge REAL NOT NULL,
        opened_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS trades (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,
        entry REAL NOT NULL,
        exit_price REAL NOT NULL,
        volume REAL NOT NULL,
        pnl REAL NOT NULL,
        reason TEXT,
        closed_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS triggers (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,
        target_price REAL NOT NULL,
        condition TEXT NOT NULL,
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    );
    """)
    # Migration: colonnes v1.4
    for col in [
        "ALTER TABLE positions ADD COLUMN tpsl_active INTEGER DEFAULT 1",
        "ALTER TABLE triggers ADD COLUMN tp_pct REAL DEFAULT 2.0",
        "ALTER TABLE triggers ADD COLUMN sl_pct REAL DEFAULT 2.0"
    ]:
        try: db.execute(col); db.commit()
        except: pass
    db.commit(); db.close()

# ── Auth ──────────────────────────────────────────────────────
def hp(pw): return hashlib.sha256((pw+SECRET_KEY).encode()).hexdigest()
def gen_tok(): return secrets.token_urlsafe(32)

def auth(token):
    if not token: return None
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE token=?", (token,)).fetchone()
    db.close()
    return dict(u) if u else None

def get_hdr_tok(headers):
    a = headers.get("Authorization","")
    return a[7:] if a.startswith("Bearer ") else None

# ── Users ─────────────────────────────────────────────────────
def get_user_by_email(email):
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE LOWER(email)=?", (email.lower(),)).fetchone()
    db.close()
    return dict(u) if u else None

def get_user_by_id(uid):
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    return dict(u) if u else None

def create_user(email, username, pw_hash, token, is_admin=False):
    uid = secrets.token_hex(16)
    db = get_db()
    try:
        db.execute("""INSERT INTO users (id,email,username,password_hash,token,is_admin)
                      VALUES (?,?,?,?,?,?)""",
                   (uid, email.lower(), username, pw_hash, token, 1 if is_admin else 0))
        db.commit()
        u = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        db.close()
        return dict(u)
    except sqlite3.IntegrityError:
        db.close(); return None

def update_user(uid, data):
    db = get_db()
    for k,v in data.items():
        db.execute(f"UPDATE users SET {k}=? WHERE id=?", (v, uid))
    db.commit(); db.close()

def update_token(email, token):
    db = get_db()
    db.execute("UPDATE users SET token=? WHERE LOWER(email)=?", (token, email.lower()))
    db.commit(); db.close()

def get_admin():
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE is_admin=1 LIMIT 1").fetchone()
    db.close()
    return dict(u) if u else None

def get_all_active_users():
    db = get_db()
    rows = db.execute("SELECT * FROM users WHERE bot_actif=1").fetchall()
    db.close()
    return [dict(r) for r in rows]

def get_all_users():
    db = get_db()
    rows = db.execute("SELECT id,email,username,balance,is_admin FROM users").fetchall()
    db.close()
    return [dict(r) for r in rows]

# ── Positions ─────────────────────────────────────────────────
def get_positions(user_id):
    """Retourne une liste de positions (plusieurs par crypto autorisées)."""
    db = get_db()
    rows = db.execute("SELECT * FROM positions WHERE user_id=? ORDER BY opened_at ASC", (user_id,)).fetchall()
    db.close()
    result = []
    for r in rows:
        keys = [d[0] for d in r.description] if hasattr(r,'description') else list(r.keys())
        result.append({
            "id":r["id"],"sym":r["symbol"],"d":r["direction"],"e":r["entry"],"v":r["volume"],
            "tp":r["tp"],"sl":r["sl"],"m":r["marge"],
            "tpsl":r["tpsl_active"] if "tpsl_active" in keys else 1,
            "ts":r["opened_at"]
        })
    return result

def get_pos_by_id(pos_id):
    db = get_db()
    r = db.execute("SELECT * FROM positions WHERE id=?", (pos_id,)).fetchone()
    db.close()
    return dict(r) if r else None

def toggle_tpsl(pos_id):
    db = get_db()
    db.execute("UPDATE positions SET tpsl_active = 1 - COALESCE(tpsl_active,1) WHERE id=?", (pos_id,))
    db.commit()
    r = db.execute("SELECT tpsl_active FROM positions WHERE id=?", (pos_id,)).fetchone()
    db.close()
    return int(r[0]) if r else 1

def get_triggers(user_id):
    try:
        db = get_db(); rows = db.execute("SELECT * FROM triggers WHERE user_id=? AND active=1 ORDER BY created_at DESC",(user_id,)).fetchall(); db.close()
        return [dict(r) for r in rows]
    except: return []

def save_trigger(user_id, symbol, direction, target, condition, tp_pct=2.0, sl_pct=2.0):
    tid = secrets.token_hex(8)
    try:
        db = get_db()
        db.execute("""INSERT INTO triggers (id,user_id,symbol,direction,target_price,condition,tp_pct,sl_pct)
                      VALUES (?,?,?,?,?,?,?,?)""",
                   (tid,user_id,symbol,direction,float(target),condition,float(tp_pct),float(sl_pct)))
        db.commit(); db.close()
    except: pass
    return tid

def delete_trigger(tid):
    try:
        db = get_db(); db.execute("UPDATE triggers SET active=0 WHERE id=?",(tid,)); db.commit(); db.close()
    except: pass

def save_position(user_id, symbol, direction, entry, volume, tp, sl, marge):
    """Plusieurs positions par crypto — plus de DELETE."""
    pid = secrets.token_hex(12)
    db = get_db()
    db.execute("""INSERT INTO positions (id,user_id,symbol,direction,entry,volume,tp,sl,marge,tpsl_active)
                  VALUES (?,?,?,?,?,?,?,?,?,1)""",
               (pid, user_id, symbol, direction, entry, volume, tp, sl, marge))
    db.commit(); db.close()
    return pid

def delete_position(user_id, symbol):
    """Ferme TOUTES les positions sur ce symbole."""
    db = get_db()
    db.execute("DELETE FROM positions WHERE user_id=? AND symbol=?", (user_id, symbol))
    db.commit(); db.close()

def delete_position_by_id(pos_id):
    db = get_db()
    db.execute("DELETE FROM positions WHERE id=?", (pos_id,))
    db.commit(); db.close()

# ── Trades ────────────────────────────────────────────────────
def get_trades(user_id, limit=100):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM trades WHERE user_id=? ORDER BY rowid DESC LIMIT ?",
        (user_id, limit)).fetchall()
    db.close()
    return [{"ts":r["closed_at"],"s":r["symbol"],"d":r["direction"],
             "e":r["entry"],"x":r["exit_price"],"v":r["volume"],
             "pnl":r["pnl"],"r":r["reason"]} for r in rows]

def save_trade(user_id, symbol, direction, entry, exit_price, volume, pnl, reason):
    tid = secrets.token_hex(8)
    db = get_db()
    db.execute("""INSERT INTO trades (id,user_id,symbol,direction,entry,exit_price,volume,pnl,reason)
                  VALUES (?,?,?,?,?,?,?,?,?)""",
               (tid, user_id, symbol, direction, entry, exit_price, volume, pnl, reason))
    db.commit(); db.close()

# ══════════════════════════════════════════════════════════════
#   GITHUB BACKUP (persistance entre redémarrages Render)
# ══════════════════════════════════════════════════════════════
_GHH = None

def gh_headers():
    global _GHH
    if not _GHH:
        _GHH = {"Authorization":f"token {GH_TOKEN}",
                "Content-Type":"application/json",
                "Accept":"application/vnd.github.v3+json"}
    return _GHH

def gh_get(path):
    if not GH_TOKEN or not DB_OWNER: return None, None
    try:
        r = requests.get(f"https://api.github.com/repos/{DB_OWNER}/{DB_REPO}/contents/{path}",
                         headers=gh_headers(), timeout=10)
        if r.status_code == 200:
            content = base64.b64decode(r.json()["content"]).decode()
            return json.loads(content), r.json()["sha"]
    except: pass
    return None, None

def gh_put(path, data, sha=None):
    if not GH_TOKEN or not DB_OWNER: return False
    try:
        body = {"message":f"backup: {path}",
                "content":base64.b64encode(json.dumps(data,ensure_ascii=False).encode()).decode(),
                "branch":"main"}
        if sha: body["sha"] = sha
        r = requests.put(f"https://api.github.com/repos/{DB_OWNER}/{DB_REPO}/contents/{path}",
                         headers=gh_headers(), json=body, timeout=20)
        return r.status_code in (200,201)
    except: return False

def load_from_github():
    """Au démarrage: charger les données GitHub → SQLite"""
    if not GH_TOKEN or not DB_OWNER:
        print("  ⚠️  Pas de GH_TOKEN/DB_OWNER — données en local seulement")
        return

    print("  Chargement depuis GitHub...")
    try:
        # Users
        users_data, _ = gh_get("users.json")
        if users_data:
            db = get_db()
            for uid, u in users_data.items():
                existing = db.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone()
                if existing:
                    db.execute("""UPDATE users SET email=?,username=?,password_hash=?,token=?,
                                  balance=?,levier=?,mise=?,tp=?,sl=?,interval=?,
                                  bot_actif=?,is_admin=?,meta_token=?,account_id=?
                                  WHERE id=?""",
                               (u["email"],u["username"],u["password_hash"],u.get("token",""),
                                u["balance"],u["levier"],u["mise"],u["tp"],u["sl"],u["interval"],
                                1 if u.get("bot_actif") else 0,
                                1 if u.get("is_admin") else 0,
                                u.get("meta_token",""),u.get("account_id",""),uid))
                else:
                    db.execute("""INSERT OR IGNORE INTO users
                                  (id,email,username,password_hash,token,balance,levier,mise,tp,sl,
                                   interval,bot_actif,is_admin,meta_token,account_id)
                                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                               (uid,u["email"],u["username"],u["password_hash"],u.get("token",""),
                                u["balance"],u["levier"],u["mise"],u["tp"],u["sl"],u["interval"],
                                1 if u.get("bot_actif") else 0,
                                1 if u.get("is_admin") else 0,
                                u.get("meta_token",""),u.get("account_id","")))
            db.commit(); db.close()
            print(f"  ✅ {len(users_data)} users chargés")

        # Positions — supporte format v1.3 (sym→pos) ET v1.4+ (pos_id→pos)
        pos_data, _ = gh_get("positions.json")
        if pos_data:
            db = get_db()
            db.execute("DELETE FROM positions")
            for user_id, pos_dict in pos_data.items():
                for key, p in pos_dict.items():
                    # v1.4+: key=pos_id, p contient "sym"
                    # v1.3:  key=symbol, p contient "d","e","v"...
                    if "sym" in p:
                        pos_id = key; sym = p["sym"]
                    else:
                        pos_id = secrets.token_hex(12); sym = key
                    tpsl = p.get("tpsl", 1)
                    db.execute("""INSERT OR IGNORE INTO positions
                                  (id,user_id,symbol,direction,entry,volume,tp,sl,marge,tpsl_active,opened_at)
                                  VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                               (pos_id,user_id,sym,p["d"],p["e"],p["v"],p["tp"],p["sl"],p["m"],tpsl,p.get("ts","")))
            db.commit(); db.close()
            total_pos = sum(len(s) for s in pos_data.values())
            print(f"  ✅ {total_pos} positions chargées")

        # Triggers actifs
        try:
            trig_data, _ = gh_get("triggers.json")
            if trig_data:
                db = get_db()
                db.execute("UPDATE triggers SET active=0")  # Reset
                for user_id, tlist in trig_data.items():
                    for t in tlist:
                        db.execute("""INSERT OR IGNORE INTO triggers
                                      (id,user_id,symbol,direction,target_price,condition,tp_pct,sl_pct,active)
                                      VALUES (?,?,?,?,?,?,?,?,1)""",
                                   (t["id"],user_id,t["sym"],t["dir"],t["target"],t["cond"],
                                    t.get("tp",2.0),t.get("sl",2.0)))
                db.commit(); db.close()
                total_t = sum(len(tl) for tl in trig_data.values())
                print(f"  ✅ {total_t} triggers chargés")
        except: pass

        # Trades
        trades_data, _ = gh_get("trades.json")
        if trades_data:
            db = get_db()
            db.execute("DELETE FROM trades")
            for user_id, tlist in trades_data.items():
                for t in tlist:
                    tid = secrets.token_hex(8)
                    db.execute("""INSERT OR IGNORE INTO trades
                                  (id,user_id,symbol,direction,entry,exit_price,volume,pnl,reason,closed_at)
                                  VALUES (?,?,?,?,?,?,?,?,?,?)""",
                               (tid,user_id,t["s"],t["d"],t["e"],t["x"],t["v"],t["pnl"],t.get("r",""),t.get("ts","")))
            db.commit(); db.close()
            total_tr = sum(len(tl) for tl in trades_data.values())
            print(f"  ✅ {total_tr} trades chargés")

    except Exception as e:
        print(f"  ⚠️  Erreur chargement GitHub: {e}")

def save_to_github():
    """Sauvegarder SQLite → GitHub (appelé périodiquement)"""
    if not GH_TOKEN or not DB_OWNER: return
    try:
        db = get_db()
        # Users
        rows = db.execute("SELECT * FROM users").fetchall()
        users = {r["id"]: {"email":r["email"],"username":r["username"],
                           "password_hash":r["password_hash"],"token":r["token"] or "",
                           "balance":r["balance"],"levier":r["levier"],"mise":r["mise"],
                           "tp":r["tp"],"sl":r["sl"],"interval":r["interval"],
                           "bot_actif":bool(r["bot_actif"]),"is_admin":bool(r["is_admin"]),
                           "meta_token":r["meta_token"] or "","account_id":r["account_id"] or ""}
                for r in rows}
        # Positions — format v1.4+ : clé = pos_id, inclut tpsl_active
        rows = db.execute("SELECT * FROM positions").fetchall()
        positions = {}
        for r in rows:
            uid = r["user_id"]
            if uid not in positions: positions[uid] = {}
            keys = list(r.keys())
            positions[uid][r["id"]] = {
                "sym":r["symbol"],"d":r["direction"],"e":r["entry"],"v":r["volume"],
                "tp":r["tp"],"sl":r["sl"],"m":r["marge"],
                "tpsl":r["tpsl_active"] if "tpsl_active" in keys else 1,
                "ts":r["opened_at"]
            }
        # Trades
        rows = db.execute("SELECT * FROM trades").fetchall()
        trades = {}
        for r in rows:
            uid = r["user_id"]
            if uid not in trades: trades[uid] = []
            trades[uid].append({"ts":r["closed_at"],"s":r["symbol"],"d":r["direction"],
                                 "e":r["entry"],"x":r["exit_price"],"v":r["volume"],
                                 "pnl":r["pnl"],"r":r["reason"] or ""})
        # Triggers actifs
        triggers_save = {}
        try:
            rows = db.execute("SELECT * FROM triggers WHERE active=1").fetchall()
            for r in rows:
                uid = r["user_id"]
                if uid not in triggers_save: triggers_save[uid] = []
                triggers_save[uid].append({
                    "id":r["id"],"sym":r["symbol"],"dir":r["direction"],
                    "target":r["target_price"],"cond":r["condition"],
                    "tp":r["tp_pct"] if "tp_pct" in list(r.keys()) else 2.0,
                    "sl":r["sl_pct"] if "sl_pct" in list(r.keys()) else 2.0
                })
        except: pass
        db.close()

        # Push vers GitHub
        for fname, data in [("users.json",users),("positions.json",positions),
                            ("trades.json",trades),("triggers.json",triggers_save)]:
            _, sha = gh_get(fname)
            gh_put(fname, data, sha)
    except Exception as e:
        print(f"  ⚠️  Erreur backup GitHub: {e}")

def github_sync_loop():
    """Thread de backup GitHub toutes les 60 secondes"""
    time.sleep(15)  # Attendre que le serveur démarre
    while True:
        time.sleep(60)
        save_to_github()

def create_admin_if_missing():
    """Créer le compte admin s'il n'existe pas"""
    if not get_user_by_email(ADMIN_EMAIL):
        uid = "admin_zyproz_001"
        pw_hash = hp("Sdfvjht1")
        token = gen_tok()
        db = get_db()
        db.execute("""INSERT OR IGNORE INTO users
                      (id,email,username,password_hash,token,is_admin,balance,levier,mise,tp,sl)
                      VALUES (?,?,?,?,?,1,1000.0,200,10.0,2.0,2.0)""",
                   (uid, ADMIN_EMAIL, "Zyproz", pw_hash, token))
        db.commit(); db.close()
        print(f"  ✅ Compte admin créé: Zyproz / {ADMIN_EMAIL} / Sdfvjht1")

# ══════════════════════════════════════════════════════════════
#   PRIX & SIGNAUX
# ══════════════════════════════════════════════════════════════
_pc={}; _pt={}

_YF_HDR = {"User-Agent":"Mozilla/5.0 (compatible; ZyCrypto/2.0)"}

def get_yahoo_price(ticker):
    """Prix via Yahoo Finance (forex, métaux, indices, ETF, matières)."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d"
        r = requests.get(url, headers=_YF_HDR, timeout=8)
        return float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except: return 0

def get_price(sym):
    """Prix universel — cache 5s. Binance pour crypto, Yahoo pour le reste."""
    if sym in _pc and time.time()-_pt.get(sym,0)<5: return _pc[sym]
    info = SYMBOLS.get(sym, {})
    src  = info.get("src", "binance")
    pair = info.get("pair", sym+"USDT")
    try:
        if src == "binance":
            v = float(requests.get(
                f"https://api.binance.com/api/v3/ticker/price?symbol={pair}",
                timeout=5).json()["price"])
        else:
            v = get_yahoo_price(pair)
        if v > 0: _pc[sym]=v; _pt[sym]=time.time()
        return v if v > 0 else _pc.get(sym, 0)
    except: return _pc.get(sym, 0)

def get_all_prices():
    """Batch fetch : Binance en une requête + Yahoo en parallèle."""
    result = {}
    # ── Crypto : une seule requête Binance ──────────────────────
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=8).json()
        pmap = {s["symbol"]: float(s["price"]) for s in r}
        for sym, info in SYMBOLS.items():
            if info.get("src") == "binance":
                p = pmap.get(info["pair"], 0)
                if p: _pc[sym]=p; _pt[sym]=time.time(); result[sym]=p
    except: pass
    # ── Non-crypto : Yahoo (utilise le cache si récent) ─────────
    import concurrent.futures
    yahoo_syms = [s for s,i in SYMBOLS.items() if i.get("src")=="yahoo"]
    def fetch_one(sym):
        p = get_price(sym)
        return sym, p
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            for sym, p in ex.map(fetch_one, yahoo_syms):
                if p > 0: result[sym] = p
    except:
        for sym in yahoo_syms:
            p = get_price(sym)
            if p > 0: result[sym] = p
    return result

# ═══════════════════════════════════════════════════════════
#   MOTEUR D'ANALYSE v2.0 — Multi-indicateurs professionnels
# ═══════════════════════════════════════════════════════════

_fg_cache = {"value": 50, "ts": 0}  # Fear & Greed Index cache

def get_yahoo_candles(ticker, tf="5m", limit=100):
    """Bougies OHLCV depuis Yahoo Finance."""
    try:
        # Conversion timeframe Binance → Yahoo
        tf_map = {"1m":"1m","5m":"5m","15m":"15m","1h":"60m","4h":"60m","1d":"1d"}
        yf_tf  = tf_map.get(tf, "5m")
        range_map = {"1m":"1d","5m":"5d","15m":"1mo","60m":"3mo","1d":"1y"}
        yf_range = range_map.get(yf_tf, "5d")
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
               f"?interval={yf_tf}&range={yf_range}")
        r = requests.get(url, headers=_YF_HDR, timeout=10)
        d = r.json()["chart"]["result"][0]
        ts = d["timestamp"]
        q  = d["indicators"]["quote"][0]
        out = []
        for i in range(len(ts)):
            try:
                c = {"t":ts[i],"o":float(q["open"][i] or 0),"h":float(q["high"][i] or 0),
                     "l":float(q["low"][i] or 0),"c":float(q["close"][i] or 0),
                     "v":float(q["volume"][i] or 0)}
                if c["c"]>0: out.append(c)
            except: pass
        return out[-limit:] if len(out)>limit else out
    except: return []

def get_candles_full(sym, tf="5m", limit=100):
    """Bougies complètes OHLCV — Binance ou Yahoo selon la source."""
    info = SYMBOLS.get(sym, {})
    src  = info.get("src", "binance")
    pair = info.get("pair", sym+"USDT")
    try:
        if src == "binance":
            r = requests.get(
                f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={tf}&limit={limit}",
                timeout=10)
            return [{"o":float(k[1]),"h":float(k[2]),"l":float(k[3]),
                     "c":float(k[4]),"v":float(k[5]),"t":int(k[0])/1000}
                    for k in r.json()]
        else:
            return get_yahoo_candles(pair, tf, limit)
    except: return []

def candles(sym, n=70):
    """Compat : retourne seulement les closes."""
    data = get_candles_full(sym, "5m", n)
    return [c["c"] for c in data] if data else [get_price(sym) or 100]*n

def calc_ema(closes, period):
    """Exponential Moving Average."""
    if not closes or len(closes) < period: return closes[-1] if closes else 0
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return ema

def calc_rsi(closes, period=14):
    """RSI — Relative Strength Index."""
    if len(closes) < period + 1: return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    ag = sum(gains[:period]) / period; al = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        ag = (ag*(period-1)+gains[i])/period; al = (al*(period-1)+losses[i])/period
    return round(100 - (100 / (1 + ag/al)), 2) if al else 100.0

def calc_macd(closes, fast=12, slow=26, sig=9):
    """MACD + Signal line. Retourne (macd, signal, histogram)."""
    if len(closes) < slow + sig: return 0, 0, 0
    macd_hist = []
    for i in range(slow - 1, len(closes)):
        ef = calc_ema(closes[:i+1], fast)
        es = calc_ema(closes[:i+1], slow)
        macd_hist.append(ef - es)
    if len(macd_hist) < sig: return 0, 0, 0
    signal_line = calc_ema(macd_hist, sig)
    macd_val = macd_hist[-1]
    return round(macd_val, 6), round(signal_line, 6), round(macd_val - signal_line, 6)

def calc_bollinger(closes, period=20, std_mult=2.0):
    """Bandes de Bollinger. Retourne (upper, mid, lower)."""
    if len(closes) < period: return closes[-1], closes[-1], closes[-1]
    recent = closes[-period:]
    mid = sum(recent) / period
    variance = sum((x - mid)**2 for x in recent) / period
    std = variance**0.5
    return round(mid + std_mult*std, 6), round(mid, 6), round(mid - std_mult*std, 6)

def calc_atr(candles_data, period=14):
    """Average True Range — mesure la volatilité."""
    if len(candles_data) < period + 1: return 0
    trs = []
    for i in range(1, len(candles_data)):
        h = candles_data[i]["h"]; l = candles_data[i]["l"]; pc = candles_data[i-1]["c"]
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
    return round(sum(trs[-period:]) / period, 6)

def calc_stoch_rsi(closes, rsi_p=14, stoch_p=14):
    """Stochastic RSI — détecte les zones de surachat/survente."""
    if len(closes) < rsi_p + stoch_p: return 50.0
    rsi_vals = []
    for i in range(rsi_p, len(closes)+1):
        rsi_vals.append(calc_rsi(closes[:i], rsi_p))
    recent_rsi = rsi_vals[-stoch_p:]
    mn, mx = min(recent_rsi), max(recent_rsi)
    if mx == mn: return 50.0
    return round((rsi_vals[-1] - mn) / (mx - mn) * 100, 2)

def get_fear_greed():
    """Crypto Fear & Greed Index (alternative.me) — mise à jour horaire."""
    if time.time() - _fg_cache["ts"] > 3600:
        try:
            r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
            _fg_cache["value"] = int(r.json()["data"][0]["value"])
            _fg_cache["ts"] = time.time()
        except: pass
    return _fg_cache["value"]

def ma(c, p): return sum(c[-p:])/p if len(c) >= p else c[-1]

def rsi(c, p=14): return calc_rsi(c, p)

def get_signal(sym):
    """
    Moteur de signal v2.0 — Système de score multi-indicateurs.
    Score 0-10 par direction. Trade uniquement si score >= 6.
    
    Indicateurs utilisés :
    • RSI 5m + RSI 1h (sur-acheté/sur-vendu)
    • MACD 5m (momentum)
    • Bandes de Bollinger 5m (position du prix)
    • EMA 20/50 (tendance principale)
    • Stochastic RSI (confirmation)
    • Volume (confirmation du signal)
    • Fear & Greed Index (sentiment marché)
    """
    try:
        # ── Données multi-timeframes ──────────────────────────────
        c5m = get_candles_full(sym, "5m", 100)
        c1h = get_candles_full(sym, "1h", 60)

        if not c5m or len(c5m) < 50:
            return None, get_price(sym) or 0, 0

        cl5 = [c["c"] for c in c5m]
        cl1h = [c["c"] for c in c1h] if c1h else cl5
        vol5 = [c["v"] for c in c5m]
        price = cl5[-1]

        # ── Calcul des indicateurs ────────────────────────────────
        rsi5m    = calc_rsi(cl5, 14)
        rsi1h    = calc_rsi(cl1h, 14) if len(cl1h) >= 15 else 50
        macd_v, macd_sig, macd_hist = calc_macd(cl5)
        bb_up, bb_mid, bb_low       = calc_bollinger(cl5)
        ema20    = calc_ema(cl5, 20)
        ema50    = calc_ema(cl5, 50)
        stoch    = calc_stoch_rsi(cl5)
        atr      = calc_atr(c5m)
        fg       = get_fear_greed()

        # ── Volume ────────────────────────────────────────────────
        avg_vol = sum(vol5[-20:]) / 20 if len(vol5) >= 20 else vol5[-1]
        vol_surge = vol5[-1] > avg_vol * 1.3  # +30% volume = confirmation

        # ══ SCORING BUY ══════════════════════════════════════════
        buy = 0
        buy_reasons = []

        if rsi5m < 35:          buy += 2.0; buy_reasons.append(f"RSI5m:{rsi5m:.0f}↓")
        elif rsi5m < 45:        buy += 1.0; buy_reasons.append(f"RSI5m:{rsi5m:.0f}")

        if rsi1h < 45:          buy += 1.0; buy_reasons.append(f"RSI1h:{rsi1h:.0f}")

        if macd_hist > 0:       buy += 1.5; buy_reasons.append("MACD+")
        if macd_v > macd_sig and macd_v < 0: buy += 1.0; buy_reasons.append("MACD↗")

        if price < bb_low:      buy += 2.0; buy_reasons.append("BB_sous")
        elif price < bb_mid:    buy += 0.5; buy_reasons.append("BB_mid-")

        if price > ema20 > ema50:  buy += 1.0; buy_reasons.append("EMA↑")
        elif price > ema20:        buy += 0.5; buy_reasons.append("EMA20↑")

        if stoch < 20:          buy += 1.5; buy_reasons.append(f"StRSI:{stoch:.0f}↓")
        elif stoch < 35:        buy += 0.5; buy_reasons.append(f"StRSI:{stoch:.0f}")

        if fg <= 25:            buy += 1.5; buy_reasons.append(f"F&G:{fg}PEUR")
        elif fg <= 40:          buy += 0.5; buy_reasons.append(f"F&G:{fg}")

        if vol_surge and buy > 0: buy += 0.5; buy_reasons.append("VOL↑")

        # ══ SCORING SELL ═════════════════════════════════════════
        sell = 0
        sell_reasons = []

        if rsi5m > 65:          sell += 2.0; sell_reasons.append(f"RSI5m:{rsi5m:.0f}↑")
        elif rsi5m > 55:        sell += 1.0; sell_reasons.append(f"RSI5m:{rsi5m:.0f}")

        if rsi1h > 55:          sell += 1.0; sell_reasons.append(f"RSI1h:{rsi1h:.0f}")

        if macd_hist < 0:       sell += 1.5; sell_reasons.append("MACD-")
        if macd_v < macd_sig and macd_v > 0: sell += 1.0; sell_reasons.append("MACD↘")

        if price > bb_up:       sell += 2.0; sell_reasons.append("BB_sur")
        elif price > bb_mid:    sell += 0.5; sell_reasons.append("BB_mid+")

        if price < ema20 < ema50:  sell += 1.0; sell_reasons.append("EMA↓")
        elif price < ema20:        sell += 0.5; sell_reasons.append("EMA20↓")

        if stoch > 80:          sell += 1.5; sell_reasons.append(f"StRSI:{stoch:.0f}↑")
        elif stoch > 65:        sell += 0.5; sell_reasons.append(f"StRSI:{stoch:.0f}")

        if fg >= 75:            sell += 1.5; sell_reasons.append(f"F&G:{fg}GREED")
        elif fg >= 60:          sell += 0.5; sell_reasons.append(f"F&G:{fg}")

        if vol_surge and sell > 0: sell += 0.5; sell_reasons.append("VOL↑")

        # ══ DÉCISION (seuil 6/10) ════════════════════════════════
        buy  = round(min(buy, 10), 1)
        sell = round(min(sell, 10), 1)

        if buy >= 6 and buy > sell:
            score_str = f"{buy}/10 | " + " · ".join(buy_reasons[:5])
            return "BUY", price, score_str
        if sell >= 6 and sell > buy:
            score_str = f"{sell}/10 | " + " · ".join(sell_reasons[:5])
            return "SELL", price, score_str

        return None, price, f"B:{buy} S:{sell}"

    except Exception as e:
        try: return None, get_price(sym) or 0, "ERR"
        except: return None, 0, "ERR"

def calc_pnl(d,e,v,cp):
    return round(float(v)*(float(cp)-float(e)),4) if d=="BUY" else round(float(v)*(float(e)-float(cp)),4)

def get_ohlc(sym,tf="5m",limit=100):
    try:
        pair = SYMBOLS.get(sym,{}).get("pair","BTCUSDT")
        r=requests.get(f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={tf}&limit={limit}",
                       timeout=10)
        return [{"t":int(k[0])/1000,"o":float(k[1]),"h":float(k[2]),"l":float(k[3]),"c":float(k[4])}
                for k in r.json()]
    except: return []

# ══════════════════════════════════════════════════════════════
#   TRADING ENGINE
# ══════════════════════════════════════════════════════════════
_threads={}
_cooldown={}  # {(uid,sym): timestamp}

def tg(msg):
    """Envoie une notification Telegram (privé + groupe si configuré)."""
    targets = [TG_ADMIN_ID]
    if TG_GROUP_ID:
        try: targets.append(int(TG_GROUP_ID))
        except: pass
    for chat_id in targets:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                         json={"chat_id":chat_id,"text":msg,"parse_mode":"Markdown"},
                         timeout=8)
        except: pass


# ═══════════════════════════════════════════════════════════════
#   METAAPI — Client REST pour Vantage Markets (vrai argent)
# ═══════════════════════════════════════════════════════════════

# Mapping ZyCrypto → MT5 Vantage
META_SYMBOLS = {
    "BTC":"BTCUSD","ETH":"ETHUSD","BNB":"BNBUSD","SOL":"SOLUSD",
    "XRP":"XRPUSD","DOGE":"DOGEUSD","ADA":"ADAUSD","LTC":"LTCUSD",
    "DOT":"DOTUSD","LINK":"LINKUSD","AVAX":"AVAXUSD","MATIC":"MATICUSD",
    "UNI":"UNIUSD","ATOM":"ATOMUSD","NEAR":"NEARUSD",
    "GOLD":"XAUUSD","SILVER":"XAGUSD","PLAT":"XPTUSD","COPPER":"XCUUSD",
    "EURUSD":"EURUSD","GBPUSD":"GBPUSD","USDJPY":"USDJPY","USDCHF":"USDCHF",
    "AUDUSD":"AUDUSD","USDCAD":"USDCAD","NZDUSD":"NZDUSD","EURGBP":"EURGBP",
    "EURJPY":"EURJPY","GBPJPY":"GBPJPY",
    "US500":"US500","US100":"NAS100","US30":"US30",
    "DE40":"DE40","UK100":"UK100","JP225":"JP225","FR40":"FR40",
    "OIL":"USOIL","BRENT":"UKOIL","NATGAS":"NATGAS",
    "WHEAT":"WHEAT","CORN":"CORN","COFFEE":"COFFEE",
    "SPY":"SPY","QQQ":"QQQ","GLD":"GLD",
}

# Tailles de contrat MT5 (pour calcul des lots)
META_LOTS = {
    "EURUSD":100000,"GBPUSD":100000,"USDJPY":100000,"USDCHF":100000,
    "AUDUSD":100000,"USDCAD":100000,"NZDUSD":100000,"EURGBP":100000,
    "EURJPY":100000,"GBPJPY":100000,
    "XAUUSD":100,"XAGUSD":5000,"XPTUSD":50,
    "US500":1,"NAS100":1,"US30":1,"DE40":1,"UK100":1,"JP225":1,
    "BTCUSD":1,"ETHUSD":1,"LTCUSD":1,"BNBUSD":1,
    "USOIL":1000,"UKOIL":1000,"NATGAS":10000,
}

_meta_url = lambda path: f"https://mt-client-api-v1.{META_REGION}.agiliumtrade.ai{path}"
_meta_prov = lambda path: f"https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai{path}"
_meta_hdr  = lambda: {"auth-token":META_TOKEN,"Content-Type":"application/json"}

def meta_account_info():
    """Solde et équité réels depuis MT5."""
    if not META_TOKEN: return None
    try:
        r = requests.get(
            _meta_url(f"/users/current/accounts/{META_ACCOUNT}/account-information"),
            headers=_meta_hdr(), timeout=15)
        return r.json() if r.status_code==200 else None
    except: return None

def meta_positions_live():
    """Positions ouvertes sur MT5."""
    if not META_TOKEN: return []
    try:
        r = requests.get(
            _meta_url(f"/users/current/accounts/{META_ACCOUNT}/positions"),
            headers=_meta_hdr(), timeout=15)
        return r.json() if r.status_code==200 else []
    except: return []

def meta_connection_status():
    """Statut de connexion MT5 : CONNECTED|DISCONNECTED|DEPLOYING|ERROR."""
    if not META_TOKEN: return "NO_CONFIG"
    try:
        r = requests.get(
            _meta_url(f"/users/current/accounts/{META_ACCOUNT}/connection-status"),
            headers=_meta_hdr(), timeout=10)
        if r.status_code==200: return r.json().get("status","UNKNOWN")
    except: pass
    return "ERROR"

def meta_deploy():
    """Déploie le compte MetaAPI (one-time)."""
    if not META_TOKEN: return False
    try:
        r = requests.post(
            _meta_prov(f"/users/current/accounts/{META_ACCOUNT}/deploy"),
            headers=_meta_hdr(), timeout=30)
        return r.status_code in (200,204)
    except: return False

def meta_calc_lots(sym, mise, lev, price):
    """Calcule le volume en lots MT5 (min 0.01)."""
    mt = META_SYMBOLS.get(sym, sym)
    cs = META_LOTS.get(mt, 1)
    notional = float(mise) * min(int(lev), 500)
    if price<=0 or cs<=0: return 0.01
    volume = notional / (price * cs)
    return max(0.01, round(volume*100)/100)  # Arrondi au 0.01 lot

def meta_trade(sym, direction, price, mise, lev, tp_price, sl_price):
    """Ouvre un vrai trade via MetaAPI. Retourne le ticket MT5 ou None."""
    if not META_TOKEN: return None
    mt = META_SYMBOLS.get(sym, sym)
    vol = meta_calc_lots(sym, mise, lev, price)
    body = {
        "actionType": "ORDER_TYPE_BUY" if direction=="BUY" else "ORDER_TYPE_SELL",
        "symbol": mt, "volume": vol, "comment": "ZyCrypto"
    }
    if tp_price and tp_price>0: body["takeProfit"] = round(float(tp_price),5)
    if sl_price and sl_price>0: body["stopLoss"]   = round(float(sl_price),5)
    try:
        r = requests.post(
            _meta_url(f"/users/current/accounts/{META_ACCOUNT}/trade"),
            headers=_meta_hdr(), json=body, timeout=25)
        if r.status_code in (200,201):
            d = r.json()
            code_ = d.get("numericCode",0)
            if code_ in (10008,10009,10010):  # DONE/PLACED
                ticket = d.get("positionId") or d.get("orderId","")
                return {"ticket":str(ticket),"vol":vol}
            else:
                print(f"⚠️ MetaAPI trade: {d.get('message',d)}")
    except Exception as e:
        print(f"⚠️ MetaAPI exception: {e}")
    return None

def meta_close(ticket):
    """Ferme un trade MT5 par son ticket."""
    if not META_TOKEN: return False
    body = {"actionType":"POSITION_CLOSE_ID","positionId":str(ticket)}
    try:
        r = requests.post(
            _meta_url(f"/users/current/accounts/{META_ACCOUNT}/trade"),
            headers=_meta_hdr(), json=body, timeout=25)
        if r.status_code in (200,201):
            d = r.json()
            return d.get("numericCode",0) in (10008,10009,10010)
    except: pass
    return False

def open_trade(user_id, sym, direction, price, tp_pct=None, sl_pct=None):
    cfg = get_user_by_id(user_id)
    if not cfg: return None
    mise = float(cfg["mise"]); lev = int(cfg["levier"])
    tp_p = (tp_pct if tp_pct is not None else float(cfg["tp"])) / 100
    sl_p = (sl_pct if sl_pct is not None else float(cfg["sl"])) / 100
    tp = round(price*(1+tp_p),6) if direction=="BUY" else round(price*(1-tp_p),6)
    sl = round(price*(1-sl_p),6) if direction=="BUY" else round(price*(1+sl_p),6)

    if REAL_TRADING and META_TOKEN and META_ACCOUNT:
        # ── MODE RÉEL : trade via MetaAPI ──────────────────────
        result = meta_trade(sym, direction, price, mise, lev, tp, sl)
        if not result: return None
        ticket = result["ticket"]; vol = result["vol"]
        # Sauvegarder avec ticket MT5 comme pos_id
        db = get_db()
        db.execute("""INSERT INTO positions (id,user_id,symbol,direction,entry,volume,tp,sl,marge,tpsl_active)
                      VALUES (?,?,?,?,?,?,?,?,?,1)""",
                   (ticket,user_id,sym,direction,price,vol,tp,sl,mise))
        db.commit(); db.close()
        return {"pid":ticket,"v":vol,"tp":tp,"sl":sl,"m":mise}
    else:
        # ── MODE DÉMO : simulation ──────────────────────────────
        bal = float(cfg["balance"])
        if bal < mise: return None
        vol = max(round((mise*lev/price)/0.0001)*0.0001, 0.0001)
        db = get_db()
        db.execute("UPDATE users SET balance=balance-? WHERE id=?", (mise, user_id))
        db.commit(); db.close()
        pid = save_position(user_id, sym, direction, price, vol, tp, sl, mise)
        return {"pid":pid,"v":vol,"tp":tp,"sl":sl,"m":mise}

def close_trade_by_id(pos_id, cp, reason):
    """Ferme une position par son ID (local ou MetaAPI)."""
    p = get_pos_by_id(pos_id)
    if not p: return None
    sym = p["symbol"]; user_id = p["user_id"]
    pnl = calc_pnl(p["direction"], p["entry"], p["volume"], cp)

    if REAL_TRADING and META_TOKEN and META_ACCOUNT:
        # ── MODE RÉEL : fermer via MetaAPI ─────────────────────
        ok = meta_close(pos_id)  # pos_id = ticket MT5
        if not ok: return None
        # PnL réel sera reflété dans le solde MT5
        save_trade(user_id, sym, p["direction"], float(p["entry"]), float(cp), float(p["volume"]), pnl, reason)
        delete_position_by_id(pos_id)
    else:
        # ── MODE DÉMO : simulation ──────────────────────────────
        db = get_db()
        db.execute("UPDATE users SET balance=balance+? WHERE id=?", (float(p["marge"])+pnl, user_id))
        db.commit(); db.close()
        save_trade(user_id, sym, p["direction"], float(p["entry"]), float(cp), float(p["volume"]), pnl, reason)
        delete_position_by_id(pos_id)
    return pnl

def close_trade(user_id, sym, cp, reason):
    """Ferme la première position sur ce symbole (compat)."""
    pos = get_positions(user_id)
    for p in pos:
        if p["sym"] == sym:
            return close_trade_by_id(p["id"], cp, reason)
    return None

def trading_loop(user_id):
    syms = list(SYMBOLS.keys()); tour=0
    while True:
        cfg = get_user_by_id(user_id)
        if not cfg or not cfg.get("bot_actif"): time.sleep(2); continue
        for sym in syms:
            cfg = get_user_by_id(user_id)
            if not cfg or not cfg.get("bot_actif"): break
            try:
                sn, price, rv = get_signal(sym)
                pos = get_positions(user_id)
                en = any(p["sym"]==sym for p in pos)
                if en:
                    p = pos[sym]; d = p["d"]; r = None
                    if d=="BUY":
                        if price>=float(p["tp"]): r="✅ Take-Profit"
                        elif price<=float(p["sl"]): r="🛡️ Stop-Loss"
                    else:
                        if price<=float(p["tp"]): r="✅ Take-Profit"
                        elif price>=float(p["sl"]): r="🛡️ Stop-Loss"
                    if r:
                        pnl = close_trade(user_id, sym, price, r)
                        if pnl is not None:
                            info = SYMBOLS[sym]
                            cfg2 = get_user_by_id(user_id)
                            tg(f"{'💰' if pnl>=0 else '💸'} *{info['icon']} {sym}* — {r}\n"
                               f"`{float(p['e']):.4f}` → `{price:.4f}`\n"
                               f"Profit:`{pnl:+.4f}€` Solde:`{cfg2['balance']:.2f}€`")
                        en=False
                in_cooldown=(time.time()-_cooldown.get((user_id,sym),0))<BOT_COOLDOWN
                if not en and not in_cooldown and sn in("BUY","SELL"):
                    cfg = get_user_by_id(user_id)
                    if cfg and float(cfg["balance"])>=float(cfg["mise"]):
                        t = open_trade(user_id, sym, sn, price)
                        if t:
                            info = SYMBOLS[sym]
                            tg(f"⚡ *{'🟢 LONG' if sn=='BUY' else '🔴 SHORT'}* {info['icon']} {sym} — BOT\n"
                               f"`{price:.4f}$` | Score: {rv}\n"
                               f"👤 {uname}")
            except Exception as e:
                pass
            time.sleep(0.3)
        if tour%120==0 and tour>0:
            pos2 = get_positions(user_id)
            if pos2:
                msg="📡 *Positions:*\n"
                for sk,p in pos2.items():
                    cp=get_price(sk); pnl2=calc_pnl(p["d"],p["e"],p["v"],cp) if cp else 0
                    msg+=f"  {SYMBOLS[sk]['icon']} {sk} `{pnl2:+.4f}€`\n"
                tg(msg)
        tour+=1
        cfg = get_user_by_id(user_id)
        interval = int(cfg["interval"]) if cfg else 5
        time.sleep(interval)

def tpsl_monitor():
    """TP/SL automatique — actif en permanence pour toutes les positions."""
    while True:
        try:
            db = get_db()
            rows = db.execute("SELECT * FROM positions").fetchall()
            db.close()
            for row in rows:
                try:
                    p = dict(row)
                    if p.get("tpsl_active", 1) == 0: continue
                    sym = p["symbol"]; price = get_price(sym)
                    if not price or price <= 0: continue
                    d = p["direction"]; tp = float(p["tp"]); sl = float(p["sl"]); reason = None
                    if d=="BUY":
                        if price>=tp: reason="✅ Take-Profit"
                        elif price<=sl: reason="🛡️ Stop-Loss"
                    else:
                        if price<=tp: reason="✅ Take-Profit"
                        elif price>=sl: reason="🛡️ Stop-Loss"
                    if reason:
                        pnl = close_trade_by_id(p["id"], price, reason)
                        if pnl is not None:
                            info = SYMBOLS.get(sym,{}); u2 = get_user_by_id(p["user_id"])
                            bal = u2["balance"] if u2 else 0
                            tg(f"{'💰' if pnl>=0 else '💸'} *{info.get('icon',sym)} {sym}* — {reason}\n"
                               f"`{float(p['entry']):.4f}` → `{price:.4f}`\n"
                               f"Profit:`{pnl:+.4f}€` Solde:`{bal:.2f}€`")
                except: pass
        except: pass
        time.sleep(5)

def trigger_monitor():
    """Ordres à prix cible — exécution automatique."""
    while True:
        try:
            db = get_db()
            rows = db.execute("SELECT * FROM triggers WHERE active=1").fetchall()
            db.close()
            for row in rows:
                try:
                    t = dict(row); price = get_price(t["symbol"])
                    if not price or price<=0: continue
                    fired = (t["condition"]=="below" and price<=t["target_price"]) or                             (t["condition"]=="above" and price>=t["target_price"])
                    if fired:
                        delete_trigger(t["id"])
                        tp_p = t.get("tp_pct") or 2.0
                        sl_p = t.get("sl_pct") or 2.0
                        result = open_trade(t["user_id"],t["symbol"],t["direction"],price,
                                            tp_pct=float(tp_p), sl_pct=float(sl_p))
                        if result:
                            info = SYMBOLS.get(t["symbol"],{})
                            tg(f"🎯 *Ordre déclenché !* {info.get('icon',t['symbol'])} {t['symbol']}\n"
                               f" {'🟢 LONG' if t['direction']=='BUY' else '🔴 SHORT'}"
                               f" @ `{price:.4f}$` | TP:{tp_p}% SL:{sl_p}%\n"
                               f"(cible: `{t['target_price']:.4f}$`)")
                except: pass
        except: pass
        time.sleep(3)

def ensure_thread(uid):
    if uid not in _threads or not _threads[uid].is_alive():
        t = threading.Thread(target=trading_loop, args=(uid,), daemon=True)
        t.start(); _threads[uid]=t

def start_all():
    for u in get_all_active_users(): ensure_thread(u["id"])

# ══════════════════════════════════════════════════════════════
#   HTML
# ══════════════════════════════════════════════════════════════
LOGIN_HTML = r"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>⚡ ZYCRYPTO</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@400;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#07070a;font-family:'Rajdhani',sans-serif;color:#fff;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;background-image:radial-gradient(ellipse at 50% 0%,rgba(245,197,24,.07) 0%,transparent 70%)}
.box{width:100%;max-width:380px}
.logo{font-family:'Orbitron',monospace;font-size:32px;font-weight:900;color:#f5c518;text-align:center;text-shadow:0 0 30px rgba(245,197,24,.5);letter-spacing:4px;margin-bottom:3px}
.sub{font-family:'Orbitron',monospace;font-size:7px;letter-spacing:7px;color:rgba(245,197,24,.3);text-align:center;margin-bottom:22px}
.tabs{display:flex;margin-bottom:20px;border-bottom:1px solid rgba(245,197,24,.12)}
.tab{flex:1;padding:10px;background:none;border:none;color:rgba(255,255,255,.3);font-family:'Orbitron',monospace;font-size:9px;letter-spacing:2px;cursor:pointer}
.tab.a{color:#f5c518;border-bottom:2px solid #f5c518}
.form{display:none}.form.a{display:block}
.f{margin-bottom:13px}
.f label{font-size:9px;color:rgba(255,255,255,.35);letter-spacing:2px;font-family:'Orbitron',monospace;display:block;margin-bottom:5px}
.f input{width:100%;background:rgba(245,197,24,.04);border:1px solid rgba(245,197,24,.12);border-radius:10px;padding:12px 14px;color:#fff;font-family:'Rajdhani',sans-serif;font-size:15px;outline:none;transition:.2s}
.f input:focus{border-color:rgba(245,197,24,.35);background:rgba(245,197,24,.06)}
.btn{width:100%;padding:14px;background:linear-gradient(135deg,rgba(245,197,24,.1),rgba(245,197,24,.2));border:1px solid rgba(245,197,24,.35);border-radius:12px;color:#f5c518;font-family:'Orbitron',monospace;font-size:10px;font-weight:700;letter-spacing:2px;cursor:pointer;margin-top:4px}
.msg{text-align:center;padding:10px;border-radius:8px;font-size:12px;margin-top:10px;display:none}
.msg.ok{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.25);color:#4ade80}
.msg.er{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.25);color:#f87171}
</style></head><body>
<div class="box">
  <div class="logo">⚡ ZYCRYPTO</div>
  <div class="sub">TRADING PLATFORM v1.3</div>
  <div class="tabs">
    <button class="tab a" onclick="sw(0)">CONNEXION</button>
    <button class="tab" onclick="sw(1)">INSCRIPTION</button>
  </div>
  <div class="form a" id="f0">
    <div class="f"><label>EMAIL</label><input id="le" type="email" placeholder="ton@email.com" autocomplete="email"></div>
    <div class="f"><label>MOT DE PASSE</label><input id="lp" type="password" placeholder="••••••••" autocomplete="current-password"></div>
    <button class="btn" onclick="login()">SE CONNECTER →</button>
    <div class="msg" id="lm"></div>
  </div>
  <div class="form" id="f1">
    <div class="f"><label>PSEUDO</label><input id="rn" type="text" placeholder="MonPseudo"></div>
    <div class="f"><label>EMAIL</label><input id="re" type="email" placeholder="ton@email.com" autocomplete="email"></div>
    <div class="f"><label>MOT DE PASSE</label><input id="rp" type="password" placeholder="Min. 6 caractères" autocomplete="new-password"></div>
    <button class="btn" onclick="register()">CRÉER MON COMPTE →</button>
    <div class="msg" id="rm"></div>
  </div>
</div>
<script>
function sw(n){document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('a',i===n));document.querySelectorAll('.form').forEach((f,i)=>f.classList.toggle('a',i===n));}
function msg(id,t,ok){var e=document.getElementById(id);e.textContent=t;e.className='msg '+(ok?'ok':'er');e.style.display='block';}
async function login(){
  var e=document.getElementById('le').value.trim(),p=document.getElementById('lp').value;
  if(!e||!p){msg('lm','Remplis tous les champs',false);return;}
  var btn=document.querySelector('#f0 .btn');btn.textContent='...';btn.disabled=true;
  try{var r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:e,password:p})});
  var d=await r.json();
  if(d.ok){localStorage.setItem('zt',d.token);localStorage.setItem('za',d.is_admin?'1':'0');window.location.replace('/dashboard');}
  else{msg('lm',d.error||'Email ou mot de passe incorrect',false);btn.textContent='SE CONNECTER →';btn.disabled=false;}}
  catch(err){msg('lm','Erreur réseau',false);btn.textContent='SE CONNECTER →';btn.disabled=false;}
}
async function register(){
  var n=document.getElementById('rn').value.trim(),e=document.getElementById('re').value.trim(),p=document.getElementById('rp').value;
  if(!n||!e||!p){msg('rm','Remplis tous les champs',false);return;}
  if(p.length<6){msg('rm','Mot de passe trop court',false);return;}
  var btn=document.querySelector('#f1 .btn');btn.textContent='...';btn.disabled=true;
  try{var r=await fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:n,email:e,password:p})});
  var d=await r.json();
  if(d.ok){localStorage.setItem('zt',d.token);localStorage.setItem('za',d.is_admin?'1':'0');window.location.replace('/dashboard');}
  else{msg('rm',d.error||'Erreur',false);btn.textContent='CRÉER MON COMPTE →';btn.disabled=false;}}
  catch(err){msg('rm','Erreur réseau',false);btn.textContent='CRÉER MON COMPTE →';btn.disabled=false;}
}
var t=localStorage.getItem('zt');
if(t){fetch('/api/me',{headers:{'Authorization':'Bearer '+t}}).then(r=>r.json()).then(d=>{if(d.ok)window.location.replace('/dashboard');}).catch(()=>{});}
</script></body></html>"""

DASH_HTML = r"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>⚡ ZYCRYPTO</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@600;700&display=swap" rel="stylesheet">
<script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
:root{--g:#f5c518;--bg:#07070a}
body{background:var(--bg);font-family:'Rajdhani',sans-serif;color:#fff;padding-bottom:68px}
.bnav{position:fixed;bottom:0;left:0;right:0;background:rgba(7,7,10,.97);border-top:1px solid rgba(245,197,24,.1);display:flex;z-index:100}
.bnt{flex:1;padding:10px 0;border:none;background:none;color:rgba(255,255,255,.28);font-size:18px;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:2px}
.bnt span{font-size:7px;font-family:'Orbitron',monospace;letter-spacing:1px}
.bnt.a{color:var(--g)}
.pg{display:none;padding:12px}.pg.a{display:block}
.logo{font-family:'Orbitron',monospace;font-size:20px;font-weight:900;color:var(--g);text-align:center;padding:10px 0 2px;letter-spacing:3px}
.sub{font-family:'Orbitron',monospace;font-size:7px;letter-spacing:5px;color:rgba(245,197,24,.2);text-align:center;margin-bottom:8px}
.sr{display:flex;align-items:center;justify-content:center;gap:7px;margin-bottom:8px}
.dot{width:8px;height:8px;border-radius:50%;background:#333}.dot.on{background:#22c55e;box-shadow:0 0 6px #22c55e}.dot.off{background:#ef4444}
.st{font-size:11px;color:rgba(255,255,255,.3)}
hr{border:none;height:1px;background:linear-gradient(90deg,transparent,rgba(245,197,24,.2),transparent);margin:8px 0}
.ticker{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px;margin-bottom:8px;scrollbar-width:none}
.ticker::-webkit-scrollbar{display:none}
.tk{background:rgba(245,197,24,.04);border:1px solid rgba(245,197,24,.1);border-radius:10px;padding:8px 10px;min-width:75px;flex-shrink:0}
.tk-s{font-family:'Orbitron',monospace;font-size:7px;color:rgba(245,197,24,.4);letter-spacing:1px}
.tk-i{font-size:13px;margin:1px 0}
.tk-p{font-family:'Orbitron',monospace;font-size:10px;font-weight:900;color:var(--g)}
.bal{background:rgba(245,197,24,.06);border:1px solid rgba(245,197,24,.15);border-radius:12px;padding:10px 14px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center}
.blab{font-family:'Orbitron',monospace;font-size:8px;color:rgba(255,255,255,.28);letter-spacing:1px}
.bval{font-family:'Orbitron',monospace;font-size:22px;font-weight:900;color:var(--g)}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:8px}
.sc{background:rgba(245,197,24,.03);border:1px solid rgba(245,197,24,.07);border-radius:10px;padding:7px 4px;text-align:center}
.sn{font-family:'Orbitron',monospace;font-size:14px;font-weight:900;color:var(--g)}.sl{font-size:8px;color:rgba(255,255,255,.2);margin-top:2px}
.gg{color:#22c55e}.rr{color:#ef4444}
.tt{font-family:'Orbitron',monospace;font-size:8px;letter-spacing:3px;color:rgba(245,197,24,.28);margin-bottom:6px}
.cat-row{display:flex;gap:4px;overflow-x:auto;margin-bottom:6px;scrollbar-width:none}
.cat-row::-webkit-scrollbar{display:none}
.cat-btn{background:rgba(245,197,24,.04);border:1px solid rgba(245,197,24,.1);color:rgba(255,255,255,.3);padding:4px 9px;border-radius:6px;font-family:'Orbitron',monospace;font-size:7px;cursor:pointer;white-space:nowrap;flex-shrink:0;letter-spacing:1px}
.cat-btn.a{background:rgba(245,197,24,.12);border-color:rgba(245,197,24,.35);color:var(--g)}
.sym-row{display:flex;gap:5px;overflow-x:auto;margin-bottom:8px;scrollbar-width:none}
.sym-row::-webkit-scrollbar{display:none}
.sym-btn{background:rgba(245,197,24,.05);border:1px solid rgba(245,197,24,.1);color:rgba(255,255,255,.45);padding:5px 10px;border-radius:8px;font-family:'Orbitron',monospace;font-size:8px;cursor:pointer;white-space:nowrap;flex-shrink:0}
.sym-btn.a{background:rgba(245,197,24,.15);border-color:rgba(245,197,24,.4);color:var(--g)}
.g2b{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:6px}
.btn{border:none;border-radius:10px;padding:12px 6px;font-family:'Orbitron',monospace;font-size:9px;font-weight:700;cursor:pointer;letter-spacing:1px;width:100%}
.btn:active{transform:scale(.93)}
.bst{background:linear-gradient(135deg,#14532d,#166534);color:#4ade80;border:1px solid rgba(74,222,128,.2)}
.bsp{background:linear-gradient(135deg,#7f1d1d,#991b1b);color:#f87171;border:1px solid rgba(248,113,113,.2)}
.bln{background:rgba(34,197,94,.1);color:#22c55e;border:1px solid rgba(34,197,94,.15);padding:10px 4px}
.bsh{background:rgba(239,68,68,.1);color:#ef4444;border:1px solid rgba(239,68,68,.15);padding:10px 4px}
.bcl{background:rgba(245,197,24,.07);color:var(--g);border:1px solid rgba(245,197,24,.12);padding:10px 4px}
.bca{background:rgba(168,85,247,.08);color:#c084fc;border:1px solid rgba(168,85,247,.18);padding:10px}
.admin-only{display:none}
.po{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:12px;padding:12px 14px;margin-bottom:10px;position:relative;overflow:hidden}
.po::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px}
.po.lg::before{background:#22c55e;box-shadow:0 0 6px #22c55e}
.po.sh::before{background:#ef4444;box-shadow:0 0 6px #ef4444}
.po-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.po-sym{font-family:'Orbitron',monospace;font-size:14px;font-weight:700}
.po-dir{font-size:8px;font-weight:700;letter-spacing:2px;padding:2px 8px;border-radius:20px}
.po-dir.lg{background:rgba(34,197,94,.12);color:#22c55e;border:1px solid rgba(34,197,94,.2)}
.po-dir.sh{background:rgba(239,68,68,.12);color:#ef4444;border:1px solid rgba(239,68,68,.2)}
.po-pnl{font-family:'Orbitron',monospace;font-size:18px;font-weight:900;text-align:center;padding:6px 0 8px}
.po-row{display:flex;justify-content:space-between;font-size:11px;color:rgba(255,255,255,.4);margin-bottom:4px}
.po-bar{height:4px;background:rgba(255,255,255,.07);border-radius:2px;margin-bottom:8px;overflow:hidden}
.po-close-btn{width:100%;padding:10px;background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);color:#f87171;font-family:'Orbitron',monospace;font-size:9px;font-weight:700;letter-spacing:2px;border-radius:8px;cursor:pointer}
.po-close-btn:active{transform:scale(.97)}
.badge{background:var(--g);color:#07070a;font-family:'Orbitron',monospace;font-size:8px;font-weight:900;padding:1px 5px;border-radius:10px;margin-left:4px}
.np{text-align:center;padding:30px 14px;color:rgba(255,255,255,.15);font-size:12px;font-family:'Orbitron',monospace}
.toast{position:fixed;top:12px;left:50%;transform:translateX(-50%);padding:8px 16px;border-radius:20px;font-family:'Orbitron',monospace;font-size:9px;z-index:200;opacity:0;transition:.25s;pointer-events:none;white-space:nowrap}
.toast.ok{background:rgba(34,197,94,.15);border:1px solid rgba(34,197,94,.3);color:#4ade80}
.toast.er{background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.3);color:#f87171}
.toast.sv{opacity:1}
.ctb{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap;align-items:center}
.fbt{background:rgba(245,197,24,.05);border:1px solid rgba(245,197,24,.1);color:rgba(255,255,255,.42);padding:5px 10px;border-radius:8px;font-family:'Orbitron',monospace;font-size:8px;cursor:pointer}
.fbt.a{background:rgba(245,197,24,.12);border-color:rgba(245,197,24,.3);color:var(--g)}
#chc{border-radius:12px;overflow:hidden;border:1px solid rgba(245,197,24,.08);height:350px}
.cif{display:flex;gap:12px;margin-top:6px;flex-wrap:wrap}
.cil{font-family:'Orbitron',monospace;font-size:9px;color:rgba(255,255,255,.28)}.cil b{color:var(--g)}
.hss{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:10px}
.hsc{background:rgba(245,197,24,.04);border:1px solid rgba(245,197,24,.08);border-radius:10px;padding:9px 6px;text-align:center}
.hsn{font-family:'Orbitron',monospace;font-size:15px;font-weight:900;color:var(--g)}.hsl{font-size:8px;color:rgba(255,255,255,.22);margin-top:2px}
.hi{display:flex;justify-content:space-between;align-items:center;padding:8px 11px;border-bottom:1px solid rgba(255,255,255,.04)}
.his{font-size:11px;font-weight:600}.hid{font-size:8px;color:rgba(255,255,255,.18)}.hip{font-family:'Orbitron',monospace;font-size:11px;font-weight:700}
.sf{margin-bottom:12px}
.sf label{font-size:9px;color:rgba(255,255,255,.32);letter-spacing:2px;font-family:'Orbitron',monospace;display:block;margin-bottom:5px}
.sf input{width:100%;background:rgba(245,197,24,.04);border:1px solid rgba(245,197,24,.1);border-radius:8px;padding:10px 12px;color:#fff;font-family:'Rajdhani',sans-serif;font-size:14px;outline:none;transition:.2s}
.sf input:focus{border-color:rgba(245,197,24,.3)}
.ubadge{background:rgba(245,197,24,.05);border:1px solid rgba(245,197,24,.1);border-radius:10px;padding:10px 14px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center}
.adbg{background:rgba(245,197,24,.15);border:1px solid rgba(245,197,24,.4);color:var(--g);font-family:'Orbitron',monospace;font-size:9px;padding:3px 10px;border-radius:20px;display:none}
.logout-btn{background:rgba(239,68,68,.07);border:1px solid rgba(239,68,68,.18);color:#f87171;border-radius:8px;padding:10px;width:100%;font-family:'Orbitron',monospace;font-size:9px;cursor:pointer;margin-top:10px}
.rfb{height:2px;background:rgba(245,197,24,.05);margin:8px 0 4px;border-radius:1px;overflow:hidden}
.rfi{height:100%;background:var(--g);width:100%;transition:width 3s linear}
.ft{text-align:center;font-size:7px;color:rgba(255,255,255,.07);font-family:'Orbitron',monospace;padding-bottom:6px}
</style></head><body>
<div id="toast" class="toast"></div>

<!-- PAGE 1: TRADE -->
<div id="p1" class="pg a">
<div class="logo">⚡ ZYCRYPTO</div>
<div class="sub">MULTI-CRYPTO · CLOUD · LIVE</div>
<div class="sr" style="flex-wrap:wrap;gap:6px">
  <div class="dot" id="d1"></div>
  <span class="st" id="s1">Connexion...</span>
  <span id="mode-badge" style="font-size:7px;font-family:Orbitron,monospace;padding:2px 7px;border-radius:10px;background:rgba(245,197,24,.1);border:1px solid rgba(245,197,24,.2);color:rgba(245,197,24,.6)">DÉMO</span>
</div>
<div class="ticker" id="ticker"></div>
<div class="bal">
  <div><div class="blab">SOLDE DÉMO</div><div class="bval" id="bval">--</div></div>
  <div style="text-align:right">
    <div style="font-family:'Orbitron',monospace;font-size:8px;color:rgba(255,255,255,.22)">LEVIER</div>
    <div style="font-family:'Orbitron',monospace;font-size:18px;color:var(--g);font-weight:900" id="lv">x200</div>
    <div style="font-size:8px;color:rgba(255,255,255,.2)">x<span id="ms">10</span>€</div>
  </div>
</div>
<div class="g3">
  <div class="sc"><div class="sn" id="nt">0</div><div class="sl">TRADES</div></div>
  <div class="sc"><div class="sn" id="wr">--%</div><div class="sl">WIN RATE</div></div>
  <div class="sc"><div class="sn" id="tps">+0€</div><div class="sl">PROFIT</div></div>
</div><hr>
<div class="admin-only" id="ac">
  <div class="tt">👑 ADMIN — BOT</div>
  <div class="g2b" style="margin-bottom:10px">
    <button class="btn bst" onclick="cmd('start')">▶ DÉMARRER BOT</button>
    <button class="btn bsp" onclick="cmd('stop')">⏹ ARRÊTER BOT</button>
  </div><hr>
</div>
<div class="tt">📊 CHOISIR LA CRYPTO</div>
<div class="cat-row" id="cat-row"></div>
<div class="sym-row" id="sym-sel"></div>
<div class="tt" id="trade-tt">ORDRES — BTC</div>
<div class="g2b">
  <button class="btn bln" onclick="trade('buy')">🟢 LONG</button>
  <button class="btn bsh" onclick="trade('sell')">🔴 SHORT</button>
</div>
<div class="g2b">
  <button class="btn bcl" onclick="trade('close')">🔒 FERMER</button>
  <button class="btn bca" onclick="cmd('closeall')" style="font-size:8px;padding:10px">🔒 FERMER TOUT</button>
</div>
<div class="rfb"><div class="rfi" id="rfi"></div></div>
<div class="ft">ZYCRYPTO v1.3 · ZYPROZ · 2026</div>
</div>

<!-- PAGE 2: EN COURS -->
<div id="p2" class="pg">
<div class="logo" style="font-size:16px;padding:10px 0 3px">💼 EN COURS</div>
<div class="sub">POSITIONS OUVERTES · P&amp;L TEMPS RÉEL</div>
<div class="sr"><div class="dot" id="d2"></div><span class="st" id="s2">--</span></div>
<hr>
<div id="pos-container"><div class="np">📭 Aucune position ouverte</div></div>
<div style="margin-top:10px">
  <button class="btn bca" onclick="cmd('closeall')">🔒 FERMER TOUTES LES POSITIONS</button>
</div>
<div class="rfb"><div class="rfi" id="rfi2"></div></div>
</div>

<!-- PAGE 3: GRAPHIQUE -->
<div id="p3" class="pg">
<div class="logo" style="font-size:15px;padding:10px 0 4px">📈 GRAPHIQUE LIVE</div>
<div class="ctb">
  <select id="ch-sym" onchange="lc()" style="background:rgba(245,197,24,.06);border:1px solid rgba(245,197,24,.12);color:var(--g);padding:5px 10px;border-radius:8px;font-family:'Orbitron',monospace;font-size:8px;cursor:pointer">
    <optgroup label="── CRYPTO ──">
    <option value="BTC">₿ Bitcoin</option><option value="ETH">Ξ Ethereum</option>
    <option value="BNB">◈ BNB</option><option value="SOL">◎ Solana</option>
    <option value="XRP">✕ Ripple</option><option value="DOGE">Ð Dogecoin</option>
    <option value="ADA">₳ Cardano</option><option value="LTC">Ł Litecoin</option>
    <option value="AVAX">🔺 Avalanche</option><option value="LINK">⬡ Chainlink</option>
    <option value="DOT">● Polkadot</option><option value="MATIC">⬟ Polygon</option>
    <option value="ATOM">⚛ Cosmos</option>
    </optgroup><optgroup label="── MÉTAUX ──">
    <option value="GOLD">🥇 Or (XAU)</option><option value="SILVER">🥈 Argent</option>
    <option value="PLAT">💿 Platine</option><option value="COPPER">🔶 Cuivre</option>
    </optgroup><optgroup label="── FOREX ──">
    <option value="EURUSD">€$ EUR/USD</option><option value="GBPUSD">£$ GBP/USD</option>
    <option value="USDJPY">$¥ USD/JPY</option><option value="USDCHF">$Fr USD/CHF</option>
    <option value="AUDUSD">A$ AUD/USD</option><option value="GBPJPY">£¥ GBP/JPY</option>
    </optgroup><optgroup label="── INDICES ──">
    <option value="US500">📊 S&P 500</option><option value="US100">💻 NASDAQ</option>
    <option value="US30">🏛 Dow Jones</option><option value="DE40">🇩🇪 DAX</option>
    <option value="UK100">🇬🇧 FTSE</option><option value="JP225">🗻 Nikkei</option>
    </optgroup><optgroup label="── MATIÈRES ──">
    <option value="OIL">🛢 Pétrole WTI</option><option value="NATGAS">🔥 Gaz Naturel</option>
    <option value="WHEAT">🌾 Blé</option><option value="CORN">🌽 Maïs</option>
    <option value="COFFEE">☕ Café</option>
    </optgroup><optgroup label="── ETF ──">
    <option value="SPY">🕵 SPY</option><option value="QQQ">📱 QQQ</option>
    <option value="GLD">🏅 GLD (Or)</option>
    </optgroup>
  </select>
  <span style="flex:1"></span>
  <button class="fbt" id="fb-1m" onclick="setTf('1m')">1M</button>
  <button class="fbt a" id="fb-5m" onclick="setTf('5m')">5M</button>
  <button class="fbt" id="fb-15m" onclick="setTf('15m')">15M</button>
  <button class="fbt" id="fb-1h" onclick="setTf('1h')">1H</button>
</div>
<div id="chc"></div>
<div class="cif">
  <div class="cil">O:<b id="co">--</b></div><div class="cil">H:<b id="ch2" class="gg">--</b></div>
  <div class="cil">L:<b id="cl2" class="rr">--</b></div><div class="cil">C:<b id="cc">--</b></div>
</div>
</div>

<!-- PAGE 4: HISTORIQUE -->
<div id="p4" class="pg">
<div class="logo" style="font-size:15px;padding:10px 0 4px">📋 HISTORIQUE</div>
<div class="hss">
  <div class="hsc"><div class="hsn" id="h-t">0</div><div class="hsl">TRADES</div></div>
  <div class="hsc"><div class="hsn gg" id="h-w">0</div><div class="hsl">GAGNANTS</div></div>
  <div class="hsc"><div class="hsn" id="h-p">+0€</div><div class="hsl">PROFIT</div></div>
</div>
<hr><div class="tt">📜 TOUS LES TRADES</div>
<div id="hl"><div class="np">Aucun trade</div></div>
</div>

<!-- PAGE 5: COMPTE -->
<div id="p5" class="pg">
<div class="logo" style="font-size:15px;padding:10px 0 4px">⚙️ MON COMPTE</div>
<div class="ubadge">
  <div><div style="font-size:14px;font-weight:700" id="u-name">--</div><div style="font-size:10px;color:rgba(255,255,255,.3)" id="u-email">--</div></div>
  <div class="adbg" id="adbg">👑 ADMIN</div>
</div>
<hr><div class="tt">⚡ TRADING</div>
<div class="g2b">
  <div class="sf"><label>LEVIER</label><input type="number" id="cfg-l" value="200" min="1" max="500"></div>
  <div class="sf"><label>MISE (€)</label><input type="number" id="cfg-m" value="10" min="1"></div>
</div>
<div class="g2b">
  <div class="sf"><label>TAKE PROFIT %</label><input type="number" id="cfg-tp" value="2.0" step="0.1" min="0.5"></div>
  <div class="sf"><label>STOP LOSS %</label><input type="number" id="cfg-sl" value="2.0" step="0.1" min="0.5"></div>
</div>
<button class="btn bst" onclick="saveSettings()" style="margin-bottom:12px">💾 SAUVEGARDER</button>
<hr>
<button class="logout-btn" onclick="logout()">🚪 SE DÉCONNECTER</button>
<div class="ft" style="margin-top:10px">ZYCRYPTO v1.3 · ZYPROZ · 2026</div>
</div>

<!-- PAGE 6: ORDRES LIMITES -->
<div id="p6" class="pg">
<div class="logo" style="font-size:15px;padding:10px 0 3px">🎯 ORDRES LIMITES</div>
<div class="sub">EXÉCUTION AUTO AU PRIX CIBLE</div>
<hr>
<div class="tt">➕ CRÉER UN ORDRE</div>
<div style="background:rgba(245,197,24,.04);border:1px solid rgba(245,197,24,.1);border-radius:12px;padding:12px;margin-bottom:10px">
  <div class="g2b" style="margin-bottom:8px">
    <div>
      <div style="font-size:8px;color:rgba(245,197,24,.4);font-family:Orbitron,monospace;margin-bottom:4px">CRYPTO</div>
      <select id="tr-sym" style="width:100%;background:rgba(245,197,24,.04);border:1px solid rgba(245,197,24,.12);border-radius:8px;padding:9px;color:#fff;font-family:Rajdhani,sans-serif;font-size:13px;outline:none">
        <optgroup label="── CRYPTO ──">
        <option value="BTC">₿ Bitcoin</option><option value="ETH">Ξ Ethereum</option>
        <option value="BNB">◈ BNB</option><option value="SOL">◎ Solana</option>
        <option value="XRP">✕ Ripple</option><option value="DOGE">Ð Dogecoin</option>
        <option value="ADA">₳ Cardano</option><option value="LTC">Ł Litecoin</option>
        <option value="AVAX">🔺 Avalanche</option>
        </optgroup><optgroup label="── MÉTAUX ──">
        <option value="GOLD">🥇 Or (XAU)</option><option value="SILVER">🥈 Argent</option>
        <option value="PLAT">💿 Platine</option>
        </optgroup><optgroup label="── FOREX ──">
        <option value="EURUSD">€$ EUR/USD</option><option value="GBPUSD">£$ GBP/USD</option>
        <option value="USDJPY">$¥ USD/JPY</option><option value="AUDUSD">A$ AUD/USD</option>
        </optgroup><optgroup label="── INDICES ──">
        <option value="US500">📊 S&P 500</option><option value="US100">💻 NASDAQ</option>
        <option value="US30">🏛 Dow Jones</option>
        </optgroup><optgroup label="── MATIÈRES ──">
        <option value="OIL">🛢 Pétrole WTI</option><option value="NATGAS">🔥 Gaz Naturel</option>
        <option value="WHEAT">🌾 Blé</option><option value="COFFEE">☕ Café</option>
        </optgroup>
      </select>
    </div>
    <div>
      <div style="font-size:8px;color:rgba(245,197,24,.4);font-family:Orbitron,monospace;margin-bottom:4px">ACTION</div>
      <select id="tr-dir" style="width:100%;background:rgba(34,197,94,.05);border:1px solid rgba(34,197,94,.2);border-radius:8px;padding:9px;color:#4ade80;font-family:Rajdhani,sans-serif;font-size:13px;font-weight:700;outline:none">
        <option value="BUY">🟢 LONG</option><option value="SELL">🔴 SHORT</option>
      </select>
    </div>
  </div>
  <div style="margin-bottom:8px">
    <div style="font-size:8px;color:rgba(245,197,24,.4);font-family:Orbitron,monospace;margin-bottom:4px">PRIX CIBLE ($)</div>
    <input type="number" id="tr-price" placeholder="ex: 59200" step="0.01" style="width:100%;background:rgba(245,197,24,.04);border:1px solid rgba(245,197,24,.2);border-radius:8px;padding:10px 12px;color:#fff;font-family:Rajdhani,sans-serif;font-size:15px;outline:none">
  </div>
  <div class="g2b" style="margin-bottom:8px">
    <div>
      <div style="font-size:8px;color:rgba(34,197,94,.5);font-family:Orbitron,monospace;margin-bottom:4px">TAKE PROFIT %</div>
      <input type="number" id="tr-tp" value="2.0" min="0.1" step="0.1" style="width:100%;background:rgba(34,197,94,.04);border:1px solid rgba(34,197,94,.2);border-radius:8px;padding:9px 10px;color:#4ade80;font-family:Rajdhani,sans-serif;font-size:14px;font-weight:700;outline:none">
    </div>
    <div>
      <div style="font-size:8px;color:rgba(239,68,68,.5);font-family:Orbitron,monospace;margin-bottom:4px">STOP LOSS %</div>
      <input type="number" id="tr-sl" value="2.0" min="0.1" step="0.1" style="width:100%;background:rgba(239,68,68,.04);border:1px solid rgba(239,68,68,.2);border-radius:8px;padding:9px 10px;color:#f87171;font-family:Rajdhani,sans-serif;font-size:14px;font-weight:700;outline:none">
    </div>
  </div>
  <div id="tr-info" style="text-align:center;font-size:9px;color:rgba(255,255,255,.25);font-family:Orbitron,monospace;margin-bottom:8px;letter-spacing:1px">₿ LONG quand BTC descend au prix cible</div>
  <button onclick="addTrigger()" class="btn bst">🎯 CRÉER L'ORDRE</button>
</div>
<div class="tt">📋 ORDRES ACTIFS <span id="tr-count" style="color:rgba(255,255,255,.3);font-size:8px"></span></div>
<div id="tr-list"><div class="np">Aucun ordre actif</div></div>
</div>

<nav class="bnav">
  <button class="bnt a" id="bn1" onclick="sp(1)" style="font-size:15px">📊<span>TRADE</span></button>
  <button class="bnt" id="bn2" onclick="sp(2)" style="font-size:15px">💼<span id="bn2l">EN COURS</span></button>
  <button class="bnt" id="bn3" onclick="sp(3)" style="font-size:15px">📈<span>GRAPH</span></button>
  <button class="bnt" id="bn4" onclick="sp(4)" style="font-size:15px">📋<span>HIST.</span></button>
  <button class="bnt" id="bn5" onclick="sp(5)" style="font-size:15px">⚙️<span>COMPTE</span></button>
  <button class="bnt" id="bn6" onclick="sp(6)" style="font-size:15px">🎯<span id="bn6l">ORDRES</span></button>
</nav>

<script>
var TK=localStorage.getItem('zt'), IS_ADMIN=localStorage.getItem('za')==='1';
if(!TK){window.location.replace('/');throw 0;}

var SYMS={
  BTC:{name:'Bitcoin',icon:'₿',cat:'CRYPTO'},ETH:{name:'Ethereum',icon:'Ξ',cat:'CRYPTO'},
  BNB:{name:'BNB',icon:'◈',cat:'CRYPTO'},SOL:{name:'Solana',icon:'◎',cat:'CRYPTO'},
  XRP:{name:'Ripple',icon:'✕',cat:'CRYPTO'},DOGE:{name:'Dogecoin',icon:'Ð',cat:'CRYPTO'},
  ADA:{name:'Cardano',icon:'₳',cat:'CRYPTO'},LTC:{name:'Litecoin',icon:'Ł',cat:'CRYPTO'},
  DOT:{name:'Polkadot',icon:'●',cat:'CRYPTO'},LINK:{name:'Chainlink',icon:'⬡',cat:'CRYPTO'},
  AVAX:{name:'Avalanche',icon:'🔺',cat:'CRYPTO'},MATIC:{name:'Polygon',icon:'⬟',cat:'CRYPTO'},
  UNI:{name:'Uniswap',icon:'🦄',cat:'CRYPTO'},ATOM:{name:'Cosmos',icon:'⚛',cat:'CRYPTO'},
  NEAR:{name:'NEAR',icon:'Ν',cat:'CRYPTO'},
  GOLD:{name:'Or XAU',icon:'🥇',cat:'METAL'},SILVER:{name:'Argent',icon:'🥈',cat:'METAL'},
  PLAT:{name:'Platine',icon:'💿',cat:'METAL'},COPPER:{name:'Cuivre',icon:'🔶',cat:'METAL'},
  EURUSD:{name:'EUR/USD',icon:'€$',cat:'FOREX'},GBPUSD:{name:'GBP/USD',icon:'£$',cat:'FOREX'},
  USDJPY:{name:'USD/JPY',icon:'$¥',cat:'FOREX'},USDCHF:{name:'USD/CHF',icon:'$Fr',cat:'FOREX'},
  AUDUSD:{name:'AUD/USD',icon:'A$',cat:'FOREX'},USDCAD:{name:'USD/CAD',icon:'C$',cat:'FOREX'},
  NZDUSD:{name:'NZD/USD',icon:'NZ$',cat:'FOREX'},EURGBP:{name:'EUR/GBP',icon:'€£',cat:'FOREX'},
  EURJPY:{name:'EUR/JPY',icon:'€¥',cat:'FOREX'},GBPJPY:{name:'GBP/JPY',icon:'£¥',cat:'FOREX'},
  US500:{name:'S&P 500',icon:'📊',cat:'INDEX'},US100:{name:'NASDAQ',icon:'💻',cat:'INDEX'},
  US30:{name:'Dow Jones',icon:'🏛',cat:'INDEX'},DE40:{name:'DAX',icon:'🇩🇪',cat:'INDEX'},
  UK100:{name:'FTSE 100',icon:'🇬🇧',cat:'INDEX'},JP225:{name:'Nikkei',icon:'🗻',cat:'INDEX'},
  FR40:{name:'CAC 40',icon:'🇫🇷',cat:'INDEX'},
  SPY:{name:'SPY ETF',icon:'🕵',cat:'ETF'},QQQ:{name:'QQQ ETF',icon:'📱',cat:'ETF'},
  GLD:{name:'Gold ETF',icon:'🏅',cat:'ETF'},
  OIL:{name:'Pétrole WTI',icon:'🛢',cat:'COMM'},BRENT:{name:'Brent',icon:'⛽',cat:'COMM'},
  NATGAS:{name:'Gaz Naturel',icon:'🔥',cat:'COMM'},WHEAT:{name:'Blé',icon:'🌾',cat:'COMM'},
  CORN:{name:'Maïs',icon:'🌽',cat:'COMM'},COFFEE:{name:'Café',icon:'☕',cat:'COMM'}
};
var CAT_LABELS={ALL:'TOUT',CRYPTO:'CRYPTO',METAL:'MÉTAUX',FOREX:'FOREX',INDEX:'INDICES',ETF:'ETF',COMM:'MATIÈRES'};
var SEL='BTC', cp=1;
var H={'Content-Type':'application/json','Authorization':'Bearer '+TK};
var _prices={}, _positions={};

if(IS_ADMIN) document.querySelectorAll('.admin-only').forEach(function(e){e.style.display='block';});

// Catégories
var _curCat='CRYPTO';
function buildCatBtns(){
  var cr=document.getElementById('cat-row'); if(!cr)return;
  Object.keys(CAT_LABELS).forEach(function(cat){
    var b=document.createElement('button');
    b.className='cat-btn'+(cat==='CRYPTO'?' a':'');
    b.textContent=CAT_LABELS[cat]; b.dataset.cat=cat;
    b.onclick=function(){
      _curCat=cat;
      document.querySelectorAll('.cat-btn').forEach(function(x){x.classList.remove('a');});
      b.classList.add('a');
      filterSym(cat);
    };
    cr.appendChild(b);
  });
}
function filterSym(cat){
  document.querySelectorAll('.sym-btn').forEach(function(b){
    var s=SYMS[b.dataset.sym];
    b.style.display=(cat==='ALL'||!s||s.cat===cat)?'':'none';
  });
}
function buildSymBtns(){
  var sr=document.getElementById('sym-sel'); if(!sr)return;
  Object.keys(SYMS).forEach(function(k){
    var b=document.createElement('button');
    b.className='sym-btn'+(k==='BTC'?' a':'');
    b.dataset.sym=k;
    b.textContent=SYMS[k].icon+' '+k;
    b.style.display=SYMS[k].cat==='CRYPTO'?'':'none';
    b.onclick=function(){
      SEL=k;
      document.querySelectorAll('.sym-btn').forEach(function(x){x.classList.remove('a');});
      b.classList.add('a');
      document.getElementById('trade-tt').textContent='ORDRES — '+k;
    };
    sr.appendChild(b);
  });
}
buildCatBtns();
buildSymBtns();

function sp(n){
  document.querySelectorAll('.pg').forEach(function(p){p.classList.remove('a');});
  document.querySelectorAll('.bnt').forEach(function(b){b.classList.remove('a');});
  document.getElementById('p'+n).classList.add('a');
  document.getElementById('bn'+n).classList.add('a');
  cp=n; if(n===3)lc(); if(n===4)rf4(); if(n===5)ls(); if(n===6)rfTriggers();
}

function ff(n){
  if(n===null||n===undefined||isNaN(n))return'--';
  if(n>=1000)return n.toLocaleString('fr-FR',{maximumFractionDigits:2});
  if(n>=1)return n.toFixed(2);
  return n.toFixed(6);
}
function pc(v){return v>=0?'gg':'rr';}
function ps(v){return v>=0?'+':'';}

function toast(m,ok){
  var t=document.getElementById('toast');
  t.textContent=m; t.className='toast '+(ok?'ok':'er')+' sv';
  setTimeout(function(){t.classList.remove('sv');},2500);
}

function cmd(c){
  fetch('/api/cmd',{method:'POST',headers:H,body:JSON.stringify({cmd:c})})
    .then(function(r){if(r.status===401){window.location.replace('/');return null;}return r.json();})
    .then(function(d){if(!d)return; toast(d.msg||(d.ok?'✅ OK':'❌ Erreur'),d.ok); setTimeout(rf,500);})
    .catch(function(e){toast('❌ '+e.message,false);});
}

function trade(action){
  cmd(action+'_'+SEL.toLowerCase());
}

function rf(){
  fetch('/api/status',{headers:H})
    .then(function(r){if(r.status===401){window.location.replace('/');return null;}return r.json();})
    .then(function(d){
      if(!d||!d.ok)return;
      _prices=d.prices||{}; _positions=d.positions||[];
      // Status
      var on=d.actif||false;
      document.getElementById('d1').className='dot '+(on?'on':'off');
      // Badge mode
      var mb=document.getElementById('mode-badge');
      if(mb){
        if(d.meta_status==='REAL:CONNECTED'){mb.textContent='🟢 RÉEL';mb.style.color='#4ade80';mb.style.borderColor='rgba(34,197,94,.3)';mb.style.background='rgba(34,197,94,.1)';}
        else if(d.meta_status==='REAL:OFFLINE'){mb.textContent='🟡 RÉEL OFFLINE';mb.style.color='#fbbf24';}
        else{mb.textContent='DÉMO';mb.style.color='rgba(245,197,24,.6)';}
      }
      document.getElementById('s1').textContent=on?'🟢 BOT ACTIF':'🔴 BOT ARRÊTÉ';
      document.getElementById('d2').className='dot '+(on?'on':'off');
      document.getElementById('s2').textContent=on?'BOT ACTIF':'BOT ARRÊTÉ';
      // Balance
      document.getElementById('bval').textContent=ff(d.balance)+'€';
      document.getElementById('lv').textContent='x'+d.levier;
      document.getElementById('ms').textContent=d.mise;
      // Préfill TP/SL des ordres limites avec les paramètres actuels
      var trTp=document.getElementById('tr-tp'); var trSl=document.getElementById('tr-sl');
      if(trTp&&!trTp._modified) trTp.value=d.tp||2;
      if(trSl&&!trSl._modified) trSl.value=d.sl||2;
      // Ticker
      var th='';
      Object.keys(_prices).forEach(function(s){
        var si=SYMS[s]||{icon:s};
        th+='<div class="tk"><div class="tk-s">'+s+'</div><div class="tk-i">'+si.icon+'</div><div class="tk-p">$'+ff(_prices[s])+'</div></div>';
      });
      document.getElementById('ticker').innerHTML=th;
      // Stats
      var trades=d.trades||[];
      var wins=trades.filter(function(t){return(t.pnl||0)>0;}).length;
      var tot=trades.reduce(function(s,t){return s+(t.pnl||0);},0);
      document.getElementById('nt').textContent=trades.length;
      var we=document.getElementById('wr');
      we.textContent=trades.length?Math.round(wins/trades.length*100)+'%':'--%';
      we.className='sn '+(trades.length&&wins/trades.length>=0.5?'gg':'rr');
      var te=document.getElementById('tps');
      te.textContent=ps(tot)+tot.toFixed(2)+'€';
      te.className='sn '+pc(tot);
      // Badge
      var nc=(_positions||[]).length;
      var bl=document.getElementById('bn2l');
      if(bl) bl.innerHTML='EN COURS'+(nc>0?'<span class="badge">'+nc+'</span>':'');
      // Positions
      renderPos();
      // Refresh bar
      ['rfi','rfi2'].forEach(function(id){
        var el=document.getElementById(id);
        if(!el)return;
        el.style.transition='none'; el.style.width='100%';
        setTimeout(function(){el.style.transition='width 3s linear';el.style.width='0%';},50);
      });
      if(cp===4) rf4data(trades);
    }).catch(function(){});
}

function renderPos(){
  var c=document.getElementById('pos-container');
  if(!c)return;
  var pos=_positions||[];
  var nc=pos.length;
  var bl=document.getElementById('bn2l');
  if(bl) bl.innerHTML='EN COURS'+(nc>0?'<span class="badge">'+nc+'</span>':'');
  if(!nc){
    c.innerHTML='<div class="np">📭 Aucune position ouverte</div>';
    return;
  }
  var h='';
  pos.forEach(function(p){
    var sym=p.sym; var pid=p.id;
    var cpx=_prices[sym]||0;
    var e=parseFloat(p.e)||0, v=parseFloat(p.v)||0;
    var tp=parseFloat(p.tp)||0, sl=parseFloat(p.sl)||0;
    var tpslOn=(p.tpsl===undefined||p.tpsl===1||p.tpsl===true);
    var pnl=p.d==='BUY'?v*(cpx-e):v*(e-cpx);
    var pct=e?((p.d==='BUY'?(cpx-e)/e:(e-cpx)/e)*100):0;
    var dir=p.d==='BUY'?'lg':'sh';
    var si=SYMS[sym]||{icon:sym};
    var clr=pnl>=0?'#22c55e':'#ef4444';
    var range=Math.abs(tp-sl);
    var prog=range>0?Math.min(100,Math.max(0,Math.abs((cpx-sl)/range)*100)):50;
    h+='<div class="po '+dir+'">';
    h+='<div class="po-top"><div class="po-sym">'+si.icon+' '+sym+'</div>';
    h+='<div class="po-dir '+dir+'">'+(p.d==='BUY'?'⬆ LONG':'⬇ SHORT')+'</div></div>';
    h+='<div class="po-pnl" style="color:'+clr+'">'+ps(pnl)+pnl.toFixed(4)+'€ <span style="font-size:11px;opacity:.6">('+ps(pct)+pct.toFixed(2)+'%)</span></div>';
    h+='<div class="po-row"><span>Entrée <b style="color:#fff">$'+ff(e)+'</b></span><span>Actuel <b style="color:var(--g)">$'+ff(cpx)+'</b></span></div>';
    h+='<div class="po-row" style="margin-bottom:6px"><span>Vol: '+v+'</span><span>SL $'+ff(sl)+' · TP $'+ff(tp)+'</span></div>';
    if(tpslOn){
      h+='<div class="po-bar"><div style="height:100%;width:'+prog+'%;background:'+clr+';border-radius:2px;transition:.5s"></div></div>';
    }else{
      h+='<div style="text-align:center;font-size:8px;color:rgba(255,150,0,.7);padding:4px 0;font-family:Orbitron,monospace;letter-spacing:1px">⏸ TP/SL désactivé — fermeture manuelle</div>';
    }
    h+='<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px">';
    h+=(tpslOn
      ?'<button onclick="cmd(\'toggle_'+pid+'\')" style="padding:8px;background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.25);color:#4ade80;font-family:Orbitron,monospace;font-size:7px;border-radius:8px;cursor:pointer">🔒 TP/SL ON</button>'
      :'<button onclick="cmd(\'toggle_'+pid+'\')" style="padding:8px;background:rgba(255,150,0,.1);border:1px solid rgba(255,150,0,.25);color:#fb923c;font-family:Orbitron,monospace;font-size:7px;border-radius:8px;cursor:pointer">⏸ TP/SL OFF</button>');
    h+='<button onclick="cmd(\'close_pos_'+pid+'\')" style="padding:8px;background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);color:#f87171;font-family:Orbitron,monospace;font-size:7px;border-radius:8px;cursor:pointer">✕ FERMER</button>';
    h+='</div></div>';
  });
  c.innerHTML=h;
}

function closePos(sym){cmd('close_'+sym.toLowerCase());}

function rf4(){
  fetch('/api/status',{headers:H}).then(function(r){return r.json();}).then(function(d){rf4data(d.trades||[]);}).catch(function(){});
}
function rf4data(trades){
  var wins=trades.filter(function(t){return(t.pnl||0)>0;}).length;
  var tot=trades.reduce(function(s,t){return s+(t.pnl||0);},0);
  document.getElementById('h-t').textContent=trades.length;
  var we=document.getElementById('h-w');we.textContent=wins;we.className='hsn '+(wins>0?'gg':'');
  var pe=document.getElementById('h-p');pe.textContent=ps(tot)+tot.toFixed(4)+'€';pe.className='hsn '+pc(tot);
  var le=document.getElementById('hl');
  if(!trades.length){le.innerHTML='<div class="np">Aucun trade fermé</div>';return;}
  var h='';
  trades.forEach(function(t){
    var si=SYMS[t.s]||{icon:t.s};
    var dt=t.ts?new Date(t.ts).toLocaleString('fr-FR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'';
    var pnl=t.pnl||0;
    h+='<div class="hi"><div><div class="his">'+si.icon+' '+t.s+' '+(t.d==='BUY'?'🟢 LONG':'🔴 SHORT')+'</div>';
    h+='<div class="hid">'+(t.r||'')+' · '+dt+'</div>';
    h+='<div class="hid">$'+ff(t.e||0)+' → $'+ff(t.x||0)+'</div></div>';
    h+='<div class="hip '+pc(pnl)+'">'+ps(pnl)+Math.abs(pnl).toFixed(4)+'€</div></div>';
  });
  le.innerHTML=h;
}

function ls(){
  fetch('/api/me',{headers:H}).then(function(r){return r.json();}).then(function(d){
    if(!d.ok){window.location.replace('/');return;}
    var u=d.user;
    document.getElementById('u-name').textContent=u.username;
    document.getElementById('u-email').textContent=u.email;
    document.getElementById('cfg-l').value=u.levier;
    document.getElementById('cfg-m').value=u.mise;
    document.getElementById('cfg-tp').value=u.tp;
    document.getElementById('cfg-sl').value=u.sl;
    if(u.is_admin){var ab=document.getElementById('adbg');if(ab)ab.style.display='inline-block';}
  }).catch(function(){});
}
function saveSettings(){
  var b={levier:parseInt(document.getElementById('cfg-l').value),mise:parseFloat(document.getElementById('cfg-m').value),tp:parseFloat(document.getElementById('cfg-tp').value),sl:parseFloat(document.getElementById('cfg-sl').value)};
  fetch('/api/settings',{method:'POST',headers:H,body:JSON.stringify(b)}).then(function(r){return r.json();}).then(function(d){toast(d.msg||(d.ok?'✅ Sauvegardé':'❌'),d.ok);}).catch(function(){});
}
function logout(){localStorage.clear();window.location.replace('/');}

var chart=null, cs=null, cT='5m';
function setTf(tf){cT=tf;['1m','5m','15m','1h'].forEach(function(x){document.getElementById('fb-'+x).classList.toggle('a',x===tf);});lc();}
function lc(){
  var sym=document.getElementById('ch-sym').value||'BTC';
  var con=document.getElementById('chc');
  if(!chart){
    chart=LightweightCharts.createChart(con,{width:con.clientWidth,height:350,layout:{background:{color:'#07070a'},textColor:'rgba(255,255,255,0.3)'},grid:{vertLines:{color:'rgba(245,197,24,0.03)'},horzLines:{color:'rgba(245,197,24,0.03)'}},crosshair:{mode:LightweightCharts.CrosshairMode.Normal},rightPriceScale:{borderColor:'rgba(245,197,24,0.08)'},timeScale:{borderColor:'rgba(245,197,24,0.08)',timeVisible:true}});
    cs=chart.addCandlestickSeries({upColor:'#22c55e',downColor:'#ef4444',borderUpColor:'#22c55e',borderDownColor:'#ef4444',wickUpColor:'#22c55e',wickDownColor:'#ef4444'});
    chart.subscribeCrosshairMove(function(p){if(p.seriesData&&p.seriesData.size>0){var cd=p.seriesData.values().next().value;if(cd){document.getElementById('co').textContent='$'+cd.open.toFixed(2);document.getElementById('ch2').textContent='$'+cd.high.toFixed(2);document.getElementById('cl2').textContent='$'+cd.low.toFixed(2);document.getElementById('cc').textContent='$'+cd.close.toFixed(2);}}});
  }
  fetch('/api/ohlc?s='+sym+'&tf='+cT,{headers:H}).then(function(r){return r.json();}).then(function(data){
    if(data&&data.length){cs.setData(data.map(function(c){return{time:c.t,open:c.o,high:c.h,low:c.l,close:c.c};}));chart.timeScale().fitContent();var l=data[data.length-1];document.getElementById('co').textContent='$'+l.o.toFixed(2);document.getElementById('ch2').textContent='$'+l.h.toFixed(2);document.getElementById('cl2').textContent='$'+l.l.toFixed(2);document.getElementById('cc').textContent='$'+l.c.toFixed(2);}
  }).catch(function(){});
}

function addTrigger(){
  var sym=document.getElementById('tr-sym').value;
  var dir=document.getElementById('tr-dir').value;
  var price=parseFloat(document.getElementById('tr-price').value);
  var tp=parseFloat(document.getElementById('tr-tp').value)||2.0;
  var sl=parseFloat(document.getElementById('tr-sl').value)||2.0;
  if(!price||isNaN(price)){toast('Prix invalide',false);return;}
  if(tp<=0||sl<=0){toast('TP/SL invalides',false);return;}
  var condition=dir==='BUY'?'below':'above';
  fetch('/api/trigger/add',{method:'POST',headers:H,body:JSON.stringify({symbol:sym,direction:dir,target:price,condition:condition,tp_pct:tp,sl_pct:sl})})
    .then(function(r){return r.json();})
    .then(function(d){toast(d.msg||(d.ok?'Ordre créé':'Erreur'),d.ok);if(d.ok){document.getElementById('tr-price').value='';rfTriggers();}})
    .catch(function(){toast('Erreur réseau',false);});
}
function deleteTrigger(tid){
  fetch('/api/trigger/delete',{method:'POST',headers:H,body:JSON.stringify({tid:tid})})
    .then(function(r){return r.json();})
    .then(function(d){toast(d.msg||'Supprimé',d.ok);rfTriggers();}).catch(function(){});
}
function rfTriggers(){
  fetch('/api/triggers',{headers:H}).then(function(r){return r.json();}).then(function(d){
    if(!d||!d.ok)return;
    var list=d.triggers||[];
    var cnt=document.getElementById('tr-count');
    if(cnt) cnt.textContent=list.length>0?'('+list.length+')':'';
    var bn6l=document.getElementById('bn6l');
    if(bn6l) bn6l.innerHTML='ORDRES'+(list.length>0?'<span class="badge">'+list.length+'</span>':'');
    var el=document.getElementById('tr-list');
    if(!list.length){el.innerHTML='<div class="np">Aucun ordre actif</div>';return;}
    var h='';
    list.forEach(function(t){
      var si=SYMS[t.symbol]||{icon:t.symbol}; var isL=t.direction==='BUY';
      var ct=t.condition==='below'?'≤':'≥';
      h+='<div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:10px 12px;margin-bottom:8px">';
      h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">';
      h+='<b style="font-family:Orbitron,monospace;font-size:13px">'+si.icon+' '+t.symbol+'</b>';
      h+='<span style="font-size:8px;padding:2px 8px;border-radius:20px;color:'+(isL?'#22c55e':'#ef4444')+';border:1px solid '+(isL?'rgba(34,197,94,.2)':'rgba(239,68,68,.2)')+';background:'+(isL?'rgba(34,197,94,.1)':'rgba(239,68,68,.1)')+';">'+(isL?'⬆ LONG':'⬇ SHORT')+'</span>';
      h+='</div>';
      var tp=t.tp_pct||2; var sl=t.sl_pct||2;
      h+='<div style="font-size:11px;color:rgba(255,255,255,.4);margin-bottom:4px">Si prix '+ct+' <b style="color:var(--g)">$'+ff(t.target_price)+'</b></div>';
      h+='<div style="font-size:10px;margin-bottom:8px"><span style="color:#4ade80">TP: '+tp+'%</span> &nbsp; <span style="color:#f87171">SL: '+sl+'%</span></div>';
      h+='<button onclick="deleteTrigger(\''+t.id+'\')" style="width:100%;padding:8px;background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.2);color:#f87171;font-family:Orbitron,monospace;font-size:8px;border-radius:8px;cursor:pointer">✕ ANNULER</button>';
      h+='</div>';
    });
    el.innerHTML=h;
  }).catch(function(){});
}
function updateTrInfo(){
  var sym=document.getElementById('tr-sym'); var dir=document.getElementById('tr-dir');
  var el=document.getElementById('tr-info'); if(!sym||!dir||!el)return;
  var si=SYMS[sym.value]||{icon:sym.value};
  el.textContent=si.icon+' '+(dir.value==='BUY'?'LONG quand '+sym.value+' descend au prix cible':'SHORT quand '+sym.value+' monte au prix cible');
}
var trSym=document.getElementById('tr-sym'); var trDir=document.getElementById('tr-dir');
var trTpEl=document.getElementById('tr-tp'); var trSlEl=document.getElementById('tr-sl');
if(trSym) trSym.addEventListener('change',updateTrInfo);
if(trDir) trDir.addEventListener('change',updateTrInfo);
if(trTpEl) trTpEl.addEventListener('input',function(){this._modified=true;});
if(trSlEl) trSlEl.addEventListener('input',function(){this._modified=true;});

rf();
rfTriggers();
setInterval(function(){if(cp===1||cp===2||cp===4)rf();},3000);
setInterval(function(){if(cp===3)lc();},10000);
setInterval(function(){if(cp===6)rfTriggers();},5000);
</script></body></html>"""

# ══════════════════════════════════════════════════════════════
#   HTTP SERVER
# ══════════════════════════════════════════════════════════════
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass

    def sj(self,d,c=200):
        b=json.dumps(d).encode()
        self.send_response(c)
        self.send_header("Content-Type","application/json")
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers()
        self.wfile.write(b)

    def sh(self,html):
        b=html.encode()
        self.send_response(200)
        self.send_header("Content-Type","text/html;charset=utf-8")
        self.end_headers()
        self.wfile.write(b)

    def tok(self):
        a=self.headers.get("Authorization","")
        return a[7:] if a.startswith("Bearer ") else None

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type","text/plain")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type,Authorization")
        self.end_headers()

    def do_GET(self):
        try:
            p=self.path.split("?")[0]
            if p in("/","/login"): self.sh(LOGIN_HTML)
            elif p=="/dashboard": self.sh(DASH_HTML)
            elif p in("/ping","/health"):
                self.send_response(200); self.send_header("Content-Type","text/plain"); self.end_headers(); self.wfile.write(b"OK")
            elif p=="/api/meta/status":
                u=auth(self.tok())
                if not u: self.sj({"ok":False},401); return
                status = meta_connection_status()
                ai = meta_account_info() if META_TOKEN else None
                self.sj({"ok":True,"status":status,
                    "balance":ai.get("balance",0) if ai else 0,
                    "equity":ai.get("equity",0) if ai else 0,
                    "real_trading":REAL_TRADING,
                    "account":META_ACCOUNT})

            elif p=="/api/meta/deploy":
                u=auth(self.tok())
                if not u or not u["is_admin"]: self.sj({"ok":False},403); return
                ok = meta_deploy()
                self.sj({"ok":ok,"msg":"✅ Compte déployé" if ok else "❌ Déploiement échoué"})

            elif p=="/api/me":
                u=auth(self.tok())
                if not u: self.sj({"ok":False},401); return
                self.sj({"ok":True,"user":{"username":u["username"],"email":u["email"],
                    "levier":u["levier"],"mise":u["mise"],"tp":u["tp"],"sl":u["sl"],
                    "meta_token":u.get("meta_token",""),"account_id":u.get("account_id",""),
                    "balance":u["balance"],"is_admin":bool(u["is_admin"])}})
            elif p=="/api/status":
                u=auth(self.tok())
                if not u: self.sj({"ok":False},401); return
                admin=get_admin()
                bot_on=bool(admin and admin.get("bot_actif"))
                positions=get_positions(u["id"])  # liste
                trades=get_trades(u["id"])
                prices=get_all_prices()
                # Solde : réel (MT5) ou démo (local)
                balance = round(float(u["balance"]),2)
                real_mode = REAL_TRADING and bool(META_TOKEN) and bool(META_ACCOUNT)
                meta_status = "DEMO"
                equity = balance
                if real_mode:
                    ai = meta_account_info()
                    if ai:
                        balance = round(float(ai.get("balance",balance)),2)
                        equity  = round(float(ai.get("equity",balance)),2)
                        meta_status = "REAL:CONNECTED"
                    else:
                        meta_status = "REAL:OFFLINE"
                self.sj({"ok":True,"actif":bot_on,"balance":balance,"equity":equity,
                    "real_mode":real_mode,"meta_status":meta_status,
                    "levier":u["levier"],"mise":u["mise"],"tp":u["tp"],"sl":u["sl"],
                    "prices":prices,"positions":positions,"trades":trades})
            elif p=="/api/triggers":
                u=auth(self.tok())
                if not u: self.sj({"ok":False},401); return
                self.sj({"ok":True,"triggers":get_triggers(u["id"])})
            elif p=="/api/ohlc":
                u=auth(self.tok())
                if not u: self.sj([],401); return
                qs=parse_qs(urlparse(self.path).query)
                self.sj(get_ohlc(qs.get("s",["BTC"])[0], qs.get("tf",["5m"])[0]))
            else:
                self.send_response(404); self.end_headers()
        except Exception as e:
            try: self.sj({"ok":False,"error":str(e)},500)
            except: pass

    def do_POST(self):
        try:
            n=int(self.headers.get("Content-Length",0))
            body=json.loads(self.rfile.read(n)) if n else {}
            p=self.path

            if p=="/api/register":
                email=body.get("email","").lower().strip()
                username=body.get("username","").strip()
                pw=body.get("password","")
                if not email or not username or len(pw)<6:
                    self.sj({"ok":False,"error":"Données invalides"}); return
                is_admin=bool(ADMIN_EMAIL and email==ADMIN_EMAIL)
                u=create_user(email,username,hp(pw),gen_tok(),is_admin)
                if u: self.sj({"ok":True,"token":u["token"],"is_admin":bool(u["is_admin"])})
                else: self.sj({"ok":False,"error":"Email déjà utilisé"})

            elif p=="/api/login":
                email=body.get("email","").lower().strip()
                pw=body.get("password","")
                u=get_user_by_email(email)
                if u and u["password_hash"]==hp(pw):
                    tok=gen_tok()
                    update_token(email,tok)
                    self.sj({"ok":True,"token":tok,"is_admin":bool(u["is_admin"])})
                else:
                    self.sj({"ok":False,"error":"Email ou mot de passe incorrect"})

            elif p=="/api/settings":
                u=auth(self.tok())
                if not u: self.sj({"ok":False},401); return
                new_tp=float(body.get("tp",2.0)); new_sl=float(body.get("sl",2.0))
                update_user(u["id"],{
                    "levier":int(body.get("levier",200)),
                    "mise":float(body.get("mise",10)),
                    "tp":new_tp,"sl":new_sl
                })
                # Mettre à jour les positions ouvertes avec les nouveaux TP/SL
                pos=get_positions(u["id"])
                updated=0
                if pos:
                    db=get_db()
                    for sym,p in pos.items():
                        entry=float(p["e"]); direction=p["d"]
                        if direction=="BUY":
                            ntp=round(entry*(1+new_tp/100),6)
                            nsl=round(entry*(1-new_sl/100),6)
                        else:
                            ntp=round(entry*(1-new_tp/100),6)
                            nsl=round(entry*(1+new_sl/100),6)
                        db.execute("UPDATE positions SET tp=?,sl=? WHERE user_id=? AND symbol=?",
                                   (ntp,nsl,u["id"],sym))
                        updated+=1
                    db.commit(); db.close()
                msg=f"✅ Paramètres sauvegardés"
                if updated: msg+=f" + {updated} position(s) mise(s) à jour"
                self.sj({"ok":True,"msg":msg})

            elif p=="/api/apikeys":
                u=auth(self.tok())
                if not u: self.sj({"ok":False},401); return
                update_user(u["id"],{"meta_token":body.get("meta_token",""),"account_id":body.get("account_id","")})
                self.sj({"ok":True,"msg":"✅ Clés sauvegardées"})

            elif p=="/api/admin/topup":
                u=auth(self.tok())
                if not u or not u["is_admin"]: self.sj({"ok":False},403); return
                target=body.get("target",""); amount=float(body.get("amount",0))
                db=get_db()
                row=db.execute("SELECT * FROM users WHERE LOWER(username)=? OR LOWER(email)=?",
                               (target.lower(),target.lower())).fetchone()
                db.close()
                if not row: self.sj({"ok":False,"error":f"User '{target}' introuvable"}); return
                row=dict(row)
                old_bal=float(row["balance"])
                update_user(row["id"],{"balance":round(old_bal+amount,2)})
                threading.Thread(target=save_to_github,daemon=True).start()
                self.sj({"ok":True,"username":row["username"],"old":old_bal,"new":round(old_bal+amount,2)})

            elif p=="/api/admin/reload":
                u=auth(self.tok())
                if not u or not u["is_admin"]: self.sj({"ok":False},403); return
                load_from_github()
                self.sj({"ok":True,"msg":"DB rechargée depuis GitHub"})

            elif p=="/api/admin/users":
                u=auth(self.tok())
                if not u or not u["is_admin"]: self.sj({"ok":False},403); return
                self.sj({"ok":True,"users":get_all_users()})

            elif p=="/api/trigger/add":
                u=auth(self.tok())
                if not u: self.sj({"ok":False},401); return
                sym=body.get("symbol","BTC"); direction=body.get("direction","BUY")
                target=float(body.get("target",0)); condition=body.get("condition","below")
                tp_pct=float(body.get("tp_pct",2.0)); sl_pct=float(body.get("sl_pct",2.0))
                if not target or sym not in SYMBOLS: self.sj({"ok":False,"error":"Params invalides"}); return
                tid=save_trigger(u["id"],sym,direction,target,condition,tp_pct,sl_pct)
                ic=SYMBOLS[sym]["icon"]; lbl="🟢 LONG" if direction=="BUY" else "🔴 SHORT"
                cond_txt="<=" if condition=="below" else ">="
                tg(f"🎯 *Ordre créé !* {ic} {sym} {lbl}\nSi prix {cond_txt} `${target:,.2f}` | TP:{tp_pct}% SL:{sl_pct}%")
                threading.Thread(target=save_to_github,daemon=True).start()
                self.sj({"ok":True,"tid":tid,"msg":f"🎯 {ic} {sym} {lbl} @ ${target:,.2f} | TP:{tp_pct}% SL:{sl_pct}%"})
            elif p=="/api/trigger/delete":
                u=auth(self.tok())
                if not u: self.sj({"ok":False},401); return
                tid=body.get("tid","")
                try:
                    db_=get_db(); row=db_.execute("SELECT id FROM triggers WHERE id=? AND user_id=?",(tid,u["id"])).fetchone(); db_.close()
                    if row: delete_trigger(tid); self.sj({"ok":True,"msg":"Ordre supprimé"})
                    else: self.sj({"ok":False,"error":"Introuvable"})
                except: self.sj({"ok":False,"error":"Erreur"})
            elif p=="/api/cmd":
                u=auth(self.tok())
                if not u: self.sj({"ok":False,"redirect":"/"},401); return
                c=body.get("cmd",""); uid=u["id"]; ok=True; msg=""

                if c in("start","stop"):
                    if not u["is_admin"]: self.sj({"ok":False,"msg":"❌ Admin uniquement"}); return
                    actif=1 if c=="start" else 0
                    update_user(uid,{"bot_actif":actif})
                    if actif:
                        ensure_thread(uid)
                        msg="🟢 Bot démarré !"
                        tg(f"🚀 *ZyCrypto Bot démarré* par {u['username']}")
                    else:
                        msg="⏹ Bot arrêté"

                elif c=="closeall":
                    pos=get_positions(uid); tot=0
                    if pos:
                        for p in list(pos):
                            price_k=get_price(p["sym"]) or float(p["e"])
                            pnl=close_trade_by_id(p["id"],price_k,"🔒 Fermer tout")
                            if pnl is not None: tot+=pnl
                        threading.Thread(target=save_to_github,daemon=True).start()
                        u2=get_user_by_id(uid)
                        msg=f"🔒 Tout fermé | {tot:+.4f}€ | Solde: {u2['balance']:.2f}€"
                    else:
                        ok=False; msg="Aucune position à fermer"

                elif c.startswith("close_pos_"):
                    pid=c[len("close_pos_"):]
                    row=get_pos_by_id(pid)
                    if row and row["user_id"]==uid:
                        sym_c=row["symbol"]
                        price=get_price(sym_c) or float(row["entry"])
                        pnl=close_trade_by_id(pid,price,"🔒 Fermeture manuelle")
                        if pnl is not None:
                            _cooldown[(uid,sym_c)]=time.time()
                            threading.Thread(target=save_to_github,daemon=True).start()
                            u2=get_user_by_id(uid)
                            msg=f"🔒 {row['symbol']} fermé | {pnl:+.4f}€ | Solde: {u2['balance']:.2f}€"
                        else: ok=False; msg="Position introuvable"
                    else: ok=False; msg="Position introuvable"

                elif c.startswith("toggle_"):
                    pid=c[len("toggle_"):]
                    row=get_pos_by_id(pid)
                    if row and row["user_id"]==uid:
                        state=toggle_tpsl(pid)
                        msg=f"TP/SL {'✅ activé' if state else '⏸ désactivé'} pour {row['symbol']}"
                        threading.Thread(target=save_to_github,daemon=True).start()
                    else: ok=False; msg="Position introuvable"

                else:
                    sym=None
                    for s in SYMBOLS:
                        if s.lower() in c: sym=s; break
                    if not sym:
                        self.sj({"ok":False,"msg":f"❌ Commande inconnue: {c}"}); return

                    if "buy" in c or "long" in c:
                        price=get_price(sym)
                        if price and price>0:
                            t=open_trade(uid,sym,"BUY",price)
                            if t:
                                msg=f"🟢 LONG {SYMBOLS[sym]['icon']} {sym} @ ${price:.2f}"
                                tg(f"⚡ *{msg}* ({u['username']})")
                            else: ok=False; msg="❌ Solde insuffisant"
                        else: ok=False; msg="❌ Prix indisponible"

                    elif "sell" in c or "short" in c:
                        price=get_price(sym)
                        if price and price>0:
                            t=open_trade(uid,sym,"SELL",price)
                            if t:
                                msg=f"🔴 SHORT {SYMBOLS[sym]['icon']} {sym} @ ${price:.2f}"
                                tg(f"⚡ *{msg}* ({u['username']})")
                            else: ok=False; msg="❌ Solde insuffisant"
                        else: ok=False; msg="❌ Prix indisponible"

                    elif "close" in c:
                        pos=get_positions(uid); closed=0; tot=0
                        for p in pos:
                            if p["sym"]==sym:
                                pr=get_price(sym) or float(p["e"])
                                pnl=close_trade_by_id(p["id"],pr,"🔒 Fermeture manuelle")
                                if pnl is not None: tot+=pnl; closed+=1
                        if closed:
                            u2=get_user_by_id(uid)
                            msg=f"🔒 {closed}x {sym} fermé(s) | {tot:+.4f}€ | Solde: {u2['balance']:.2f}€"
                        else: ok=False; msg=f"Pas de position {sym} ouverte"

                    else: ok=False; msg="❌ Action inconnue"

                self.sj({"ok":ok,"msg":msg})
            else:
                self.send_response(404); self.end_headers()

        except Exception as e:
            try: self.sj({"ok":False,"error":f"Erreur serveur: {str(e)}"},500)
            except: pass


def run():
    import socket as sk
    class S(HTTPServer):
        allow_reuse_address=True
        def server_bind(self):
            self.socket.setsockopt(sk.SOL_SOCKET,sk.SO_REUSEADDR,1)
            super().server_bind()

    print(f"⚡ ZYCRYPTO PLATFORM v2.0 — MetaAPI Ready")
    print(f"   Admin: {ADMIN_EMAIL}")
    print(f"   Port:  {PORT}")
    print(f"   Mode:  {'🟢 RÉEL (Vantage MT5)' if REAL_TRADING and META_TOKEN else '🟡 DÉMO'}")
    if META_TOKEN:
        print(f"   MetaAPI Account: {META_ACCOUNT}")

    init_db()
    load_from_github()
    create_admin_if_missing()
    start_all()

    # Moniteur TP/SL
    threading.Thread(target=tpsl_monitor, daemon=True).start()
    # Moniteur ordres limites
    threading.Thread(target=trigger_monitor, daemon=True).start()

    # Backup GitHub toutes les 60 secondes
    threading.Thread(target=github_sync_loop, daemon=True).start()

    S(("0.0.0.0",PORT),H).serve_forever()

if __name__=="__main__":
    run()