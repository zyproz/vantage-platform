#!/usr/bin/env python3
"""
VANTAGE PLATFORM — Serveur complet
• Multi-utilisateurs avec comptes
• Paper trading + vrai trading (MetaAPI)
• Dashboard HTML 3 onglets + graphique
• Déployable sur Render.com
"""
import json, os, sqlite3, hashlib, secrets, time, threading, requests
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ── Config ────────────────────────────────────────────────────
PORT       = int(os.environ.get("PORT", 8000))
SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
TG_TOKEN   = os.environ.get("TG_TOKEN", "8858889412:AAElLpyQCIqw3PIYeAJtxeH56DQgXBUn6Ls")
TG_ADMIN   = int(os.environ.get("TG_ADMIN", "5354522228"))
DB_PATH    = os.environ.get("DB_PATH", "vantage.db")

# ══════════════════════════════════════════════════════════════
#   DATABASE
# ══════════════════════════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        username TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        token TEXT UNIQUE,
        balance REAL DEFAULT 1000.0,
        levier INTEGER DEFAULT 200,
        mise REAL DEFAULT 10.0,
        tp REAL DEFAULT 1.0,
        sl REAL DEFAULT 0.3,
        interval INTEGER DEFAULT 5,
        bot_actif INTEGER DEFAULT 0,
        meta_token TEXT DEFAULT '',
        account_id TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,
        entry REAL NOT NULL,
        volume REAL NOT NULL,
        tp REAL NOT NULL,
        sl REAL NOT NULL,
        marge REAL NOT NULL,
        opened_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,
        entry REAL NOT NULL,
        exit_price REAL NOT NULL,
        volume REAL NOT NULL,
        pnl REAL NOT NULL,
        reason TEXT,
        closed_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)
    db.commit()
    db.close()

# ── Auth helpers ──────────────────────────────────────────────
def hash_pw(pw): return hashlib.sha256((pw+SECRET_KEY).encode()).hexdigest()
def gen_token(): return secrets.token_urlsafe(32)

def auth_user(token):
    if not token: return None
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE token=?", (token,)).fetchone()
    db.close()
    return dict(u) if u else None

# ── User data helpers ─────────────────────────────────────────
def get_positions(user_id):
    db = get_db()
    rows = db.execute("SELECT * FROM positions WHERE user_id=?", (user_id,)).fetchall()
    db.close()
    result = {}
    for r in rows:
        result[r["symbol"]] = {
            "d": r["direction"], "e": r["entry"], "v": r["volume"],
            "tp": r["tp"], "sl": r["sl"], "m": r["marge"],
            "ts": r["opened_at"], "db_id": r["id"]
        }
    return result

def get_trades(user_id, limit=50):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM trades WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit)).fetchall()
    db.close()
    return [{"ts": r["closed_at"], "s": r["symbol"], "d": r["direction"],
             "e": r["entry"], "x": r["exit_price"], "v": r["volume"],
             "pnl": r["pnl"], "r": r["reason"]} for r in rows]

def save_position(user_id, symbol, direction, entry, volume, tp, sl, marge):
    db = get_db()
    db.execute("DELETE FROM positions WHERE user_id=? AND symbol=?", (user_id, symbol))
    db.execute("""INSERT INTO positions (user_id,symbol,direction,entry,volume,tp,sl,marge)
                  VALUES (?,?,?,?,?,?,?,?)""",
               (user_id, symbol, direction, entry, volume, tp, sl, marge))
    db.commit(); db.close()

def delete_position(user_id, symbol):
    db = get_db()
    db.execute("DELETE FROM positions WHERE user_id=? AND symbol=?", (user_id, symbol))
    db.commit(); db.close()

def save_trade(user_id, symbol, direction, entry, exit_price, volume, pnl, reason):
    db = get_db()
    db.execute("""INSERT INTO trades (user_id,symbol,direction,entry,exit_price,volume,pnl,reason)
                  VALUES (?,?,?,?,?,?,?,?)""",
               (user_id, symbol, direction, entry, exit_price, volume, pnl, reason))
    db.commit(); db.close()

def update_balance(user_id, amount):
    db = get_db()
    db.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, user_id))
    db.commit(); db.close()

def get_user_cfg(user_id):
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    db.close()
    return dict(u) if u else None

# ══════════════════════════════════════════════════════════════
#   PRIX & SIGNAUX
# ══════════════════════════════════════════════════════════════
_pc={}; _pt={}
def get_btc():
    if "b" in _pc and time.time()-_pt.get("b",0)<4: return _pc["b"]
    try:
        v=float(requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",timeout=5).json()["price"])
        _pc["b"]=v; _pt["b"]=time.time(); return v
    except: return _pc.get("b",0)

def get_gold():
    if "g" in _pc and time.time()-_pt.get("g",0)<8: return _pc.get("g",0)
    try:
        v=float(requests.get("https://api.metals.live/v1/spot/gold",timeout=5).json()[0]["price"])
        _pc["g"]=v; _pt["g"]=time.time(); return v
    except:
        try:
            v=float(requests.get("https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT",timeout=5).json()["price"])
            _pc["g"]=v; _pt["g"]=time.time(); return v
        except: return _pc.get("g",0)

def px(s): return get_btc() if s=="BTC" else get_gold()

def candles(s,n=70):
    try:
        if s=="BTC": return [float(k[4]) for k in requests.get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit={n}",timeout=10).json()]
        r=requests.get("https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=5m&range=2d",headers={"User-Agent":"Mozilla/5.0"},timeout=10).json()
        cs=r["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        return [x for x in cs if x][-n:]
    except: return [px(s)]*n

def rsi(c,p=14):
    if len(c)<p+1: return 50.0
    g,l=[],[]
    for i in range(1,len(c)): d=c[i]-c[i-1]; g.append(max(d,0)); l.append(max(-d,0))
    ag=sum(g[:p])/p; al=sum(l[:p])/p
    for i in range(p,len(g)): ag=(ag*(p-1)+g[i])/p; al=(al*(p-1)+l[i])/p
    return 100-(100/(1+ag/al)) if al else 100.0

def ma(c,p): return sum(c[-p:])/p if len(c)>=p else c[-1]

def get_signal(s):
    cl=candles(s); p=px(s) or cl[-1]; r=rsi(cl)
    maf=ma(cl,5); mas=ma(cl,13); pr=cl[:-1]
    bull=(ma(pr,5)<=ma(pr,13))and(maf>mas); bear=(ma(pr,5)>=ma(pr,13))and(maf<mas)
    if r<40 and bull: return "BUY",p,round(r,1)
    if r>60 and bear: return "SELL",p,round(r,1)
    return None,p,round(r,1)

def calc_pnl(pos_row, cp):
    e=float(pos_row["e"]); v=float(pos_row["v"])
    return round(v*(cp-e),4) if pos_row["d"]=="BUY" else round(v*(e-cp),4)

def get_ohlc(sym,tf="5m",limit=100):
    try:
        bs="BTCUSDT" if sym=="BTC" else "PAXGUSDT"
        imap={"1m":"1m","5m":"5m","15m":"15m","1h":"1h","4h":"4h"}
        r=requests.get(f"https://api.binance.com/api/v3/klines?symbol={bs}&interval={imap.get(tf,'5m')}&limit={limit}",timeout=10)
        return [{"t":int(k[0])/1000,"o":float(k[1]),"h":float(k[2]),"l":float(k[3]),"c":float(k[4])} for k in r.json()]
    except: return []

# ══════════════════════════════════════════════════════════════
#   TRADING ENGINE (un thread par user actif)
# ══════════════════════════════════════════════════════════════
_trading_threads = {}

def tg_send(msg):
    try: requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",json={"chat_id":TG_ADMIN,"text":msg,"parse_mode":"Markdown"},timeout=8)
    except: pass

def open_trade(user_id, symbol, direction, price):
    cfg = get_user_cfg(user_id)
    if not cfg or cfg["balance"] < cfg["mise"]: return None
    mise=float(cfg["mise"]); levier=int(cfg["levier"])
    tp_p=float(cfg["tp"])/100; sl_p=float(cfg["sl"])/100
    volume=max(round((mise*levier/price)/0.001)*0.001, 0.001)
    if direction=="BUY":
        tp=round(price*(1+tp_p),5); sl=round(price*(1-sl_p),5)
    else:
        tp=round(price*(1-tp_p),5); sl=round(price*(1+sl_p),5)
    db=get_db(); db.execute("UPDATE users SET balance=balance-? WHERE id=?",(mise,user_id)); db.commit(); db.close()
    save_position(user_id,symbol,direction,price,volume,tp,sl,mise)
    return {"v":volume,"tp":tp,"sl":sl,"m":mise}

def close_trade(user_id, symbol, cp, reason):
    pos = get_positions(user_id)
    if symbol not in pos: return None
    p = pos[symbol]
    pnl = calc_pnl(p, cp)
    db=get_db(); db.execute("UPDATE users SET balance=balance+? WHERE id=?",(p["m"]+pnl,user_id)); db.commit(); db.close()
    save_trade(user_id,symbol,p["d"],p["e"],cp,p["v"],pnl,reason)
    delete_position(user_id,symbol)
    return pnl

def user_trading_loop(user_id):
    SYMS={"BTC":"₿ Bitcoin","GOLD":"🥇 Or"}
    tour=0
    while True:
        cfg=get_user_cfg(user_id)
        if not cfg or not cfg["bot_actif"]:
            time.sleep(2); continue
        for sym,nom in SYMS.items():
            cfg=get_user_cfg(user_id)
            if not cfg or not cfg["bot_actif"]: break
            try:
                sn,price,rv=get_signal(sym)
                pos=get_positions(user_id); en=sym in pos
                if en:
                    p=pos[sym]; d=p["d"]
                    r=None
                    if d=="BUY":
                        if price>=float(p["tp"]): r="✅ TP atteint"
                        elif price<=float(p["sl"]): r="🛡️ SL atteint"
                    else:
                        if price<=float(p["tp"]): r="✅ TP atteint"
                        elif price>=float(p["sl"]): r="🛡️ SL atteint"
                    if not r:
                        if sn=="SELL" and d=="BUY": r="🔄 Retournement"
                        elif sn=="BUY" and d=="SELL": r="🔄 Retournement"
                    if r:
                        pnl=close_trade(user_id,sym,price,r)
                        if pnl is not None:
                            cfg2=get_user_cfg(user_id)
                            tg_send(f"{'💰' if pnl>=0 else '💸'} *{nom}* — {r}\n`{float(p['e']):.2f}` → `{price:.2f}`\nProfit:`{pnl:+.4f}€` Solde:`{cfg2['balance']:.2f}€`")
                        en=False
                if not en and sn in("BUY","SELL"):
                    cfg=get_user_cfg(user_id)
                    if cfg and cfg["balance"]>=cfg["mise"]:
                        t=open_trade(user_id,sym,sn,price)
                        if t:
                            tg_send(f"⚡ *{'🟢 LONG' if sn=='BUY' else '🔴 SHORT'}* — {nom}\n`{price:.2f}$` RSI:`{rv}`\n`{cfg['mise']}€`×x{cfg['levier']}=`{cfg['mise']*cfg['levier']}€`")
            except: pass
            time.sleep(0.5)
        if tour%60==0 and tour>0:
            pos2=get_positions(user_id)
            if pos2:
                msg="📡 *Positions actives:*\n"
                for sk,p in pos2.items():
                    cp=px(sk); pnl2=calc_pnl(p,cp) if cp else 0
                    msg+=f"  {'₿' if sk=='BTC' else '🥇'} {sk} `{pnl2:+.4f}€`\n"
                tg_send(msg)
        tour+=1
        cfg=get_user_cfg(user_id)
        time.sleep(float(cfg["interval"]) if cfg else 5)

def ensure_trading_thread(user_id):
    if user_id not in _trading_threads or not _trading_threads[user_id].is_alive():
        t=threading.Thread(target=user_trading_loop,args=(user_id,),daemon=True)
        t.start(); _trading_threads[user_id]=t

# ══════════════════════════════════════════════════════════════
#   HTML PAGES
# ══════════════════════════════════════════════════════════════
LOGIN_HTML = r"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>⚡ VANTAGE PLATFORM</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@400;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#07070a;font-family:'Rajdhani',sans-serif;color:#fff;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.box{width:100%;max-width:380px}
.logo{font-family:'Orbitron',monospace;font-size:28px;font-weight:900;color:#f5c518;text-align:center;text-shadow:0 0 30px rgba(245,197,24,.6);letter-spacing:4px;margin-bottom:6px}
.sub{font-family:'Orbitron',monospace;font-size:8px;letter-spacing:8px;color:rgba(245,197,24,.35);text-align:center;margin-bottom:30px}
.tabs{display:flex;margin-bottom:20px;border-bottom:1px solid rgba(245,197,24,.15)}
.tab{flex:1;padding:10px;background:none;border:none;color:rgba(255,255,255,.35);font-family:'Orbitron',monospace;font-size:10px;letter-spacing:2px;cursor:pointer}
.tab.a{color:#f5c518;border-bottom:2px solid #f5c518}
.form{display:none}.form.a{display:block}
.field{margin-bottom:14px}
.field label{font-size:11px;color:rgba(255,255,255,.4);letter-spacing:2px;font-family:'Orbitron',monospace;display:block;margin-bottom:6px}
.field input{width:100%;background:rgba(245,197,24,.04);border:1px solid rgba(245,197,24,.15);border-radius:10px;padding:12px 14px;color:#fff;font-family:'Rajdhani',sans-serif;font-size:15px;outline:none;transition:.2s}
.field input:focus{border-color:rgba(245,197,24,.4);background:rgba(245,197,24,.07)}
.btn-main{width:100%;padding:14px;background:linear-gradient(135deg,rgba(245,197,24,.15),rgba(245,197,24,.25));border:1px solid rgba(245,197,24,.4);border-radius:12px;color:#f5c518;font-family:'Orbitron',monospace;font-size:11px;font-weight:700;letter-spacing:2px;cursor:pointer;transition:.2s;margin-top:6px}
.btn-main:hover{background:linear-gradient(135deg,rgba(245,197,24,.25),rgba(245,197,24,.35))}
.msg{text-align:center;padding:10px;border-radius:8px;font-size:12px;margin-top:10px;display:none}
.msg.ok{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.3);color:#4ade80}
.msg.er{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);color:#f87171}
.divider{height:1px;background:linear-gradient(90deg,transparent,rgba(245,197,24,.2),transparent);margin:20px 0}
.tagline{text-align:center;font-size:11px;color:rgba(255,255,255,.2);font-family:'Orbitron',monospace;letter-spacing:1px}
</style></head><body>
<div class="box">
  <div class="logo">⚡ VANTAGE</div>
  <div class="sub">TRADING PLATFORM · PAPER & LIVE</div>
  <div class="tabs">
    <button class="tab a" onclick="sw(0)">CONNEXION</button>
    <button class="tab" onclick="sw(1)">INSCRIPTION</button>
  </div>
  <div class="form a" id="f0">
    <div class="field"><label>EMAIL</label><input id="l-email" type="email" placeholder="ton@email.com"></div>
    <div class="field"><label>MOT DE PASSE</label><input id="l-pass" type="password" placeholder="••••••••"></div>
    <button class="btn-main" onclick="login()">SE CONNECTER →</button>
    <div class="msg" id="l-msg"></div>
  </div>
  <div class="form" id="f1">
    <div class="field"><label>PSEUDO</label><input id="r-name" type="text" placeholder="MonPseudo"></div>
    <div class="field"><label>EMAIL</label><input id="r-email" type="email" placeholder="ton@email.com"></div>
    <div class="field"><label>MOT DE PASSE</label><input id="r-pass" type="password" placeholder="Min. 6 caractères"></div>
    <button class="btn-main" onclick="register()">CRÉER MON COMPTE →</button>
    <div class="msg" id="r-msg"></div>
  </div>
  <div class="divider"></div>
  <div class="tagline">₿ Bitcoin · 🥇 Or · Levier x200</div>
</div>
<script>
function sw(n){document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('a',i===n));document.querySelectorAll('.form').forEach((f,i)=>f.classList.toggle('a',i===n));}
function msg(id,text,ok){const e=document.getElementById(id);e.textContent=text;e.className='msg '+(ok?'ok':'er');e.style.display='block';}
async function login(){
  const email=document.getElementById('l-email').value;const pass=document.getElementById('l-pass').value;
  if(!email||!pass){msg('l-msg','Remplis tous les champs',false);return;}
  const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password:pass})});
  const d=await r.json();
  if(d.ok){localStorage.setItem('vt',d.token);window.location='/dashboard';}
  else msg('l-msg',d.error||'Erreur',false);
}
async function register(){
  const name=document.getElementById('r-name').value;const email=document.getElementById('r-email').value;const pass=document.getElementById('r-pass').value;
  if(!name||!email||!pass){msg('r-msg','Remplis tous les champs',false);return;}
  if(pass.length<6){msg('r-msg','Mot de passe trop court',false);return;}
  const r=await fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:name,email,password:pass})});
  const d=await r.json();
  if(d.ok){localStorage.setItem('vt',d.token);window.location='/dashboard';}
  else msg('r-msg',d.error||'Erreur',false);
}
// Si déjà connecté, redirect
const t=localStorage.getItem('vt');
if(t) fetch('/api/me',{headers:{'Authorization':'Bearer '+t}}).then(r=>r.json()).then(d=>{if(d.ok)window.location='/dashboard';});
</script></body></html>"""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>⚡ VANTAGE BOT</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@600;700&display=swap" rel="stylesheet">
<script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
:root{--g:#f5c518;--bg:#07070a}
body{background:var(--bg);font-family:'Rajdhani',sans-serif;color:#fff;padding-bottom:68px}
.bnav{position:fixed;bottom:0;left:0;right:0;background:rgba(7,7,10,.96);border-top:1px solid rgba(245,197,24,.15);display:flex;z-index:100}
.bnt{flex:1;padding:10px 0;border:none;background:none;color:rgba(255,255,255,.3);font-size:20px;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:2px}
.bnt span{font-size:8px;font-family:'Orbitron',monospace;letter-spacing:1px}
.bnt.a{color:var(--g)}
.pg{display:none;padding:12px}.pg.a{display:block}
.logo{font-family:'Orbitron',monospace;font-size:18px;font-weight:900;color:var(--g);text-align:center;padding:10px 0 2px;letter-spacing:3px}
.sub{font-family:'Orbitron',monospace;font-size:7px;letter-spacing:6px;color:rgba(245,197,24,.25);text-align:center;margin-bottom:8px}
.sr{display:flex;align-items:center;justify-content:center;gap:7px;margin-bottom:8px}
.dot{width:8px;height:8px;border-radius:50%;background:#333}.dot.on{background:#22c55e;box-shadow:0 0 6px #22c55e}.dot.off{background:#ef4444}
.st{font-size:11px;color:rgba(255,255,255,.35)}
hr{border:none;height:1px;background:linear-gradient(90deg,transparent,rgba(245,197,24,.25),transparent);margin:8px 0}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px}
.cd{background:rgba(245,197,24,.04);border:1px solid rgba(245,197,24,.12);border-radius:12px;padding:10px 12px;position:relative;overflow:hidden}
.cd::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,rgba(245,197,24,.35),transparent)}
.cds{font-family:'Orbitron',monospace;font-size:8px;color:rgba(245,197,24,.4);letter-spacing:2px}
.cdi{font-size:18px;margin:2px 0}.cdv{font-family:'Orbitron',monospace;font-size:15px;font-weight:900;color:var(--g)}
.cdt{font-size:8px;color:rgba(255,255,255,.18)}
.bal{background:rgba(245,197,24,.06);border:1px solid rgba(245,197,24,.18);border-radius:12px;padding:10px 14px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center}
.blab{font-family:'Orbitron',monospace;font-size:8px;color:rgba(255,255,255,.3);letter-spacing:1px}
.bval{font-family:'Orbitron',monospace;font-size:19px;font-weight:900;color:var(--g)}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:8px}
.sc{background:rgba(245,197,24,.03);border:1px solid rgba(245,197,24,.08);border-radius:10px;padding:7px 4px;text-align:center}
.sn{font-family:'Orbitron',monospace;font-size:14px;font-weight:900;color:var(--g)}.sl{font-size:8px;color:rgba(255,255,255,.22);margin-top:2px}
.gg{color:#22c55e}.rr{color:#ef4444}
.tt{font-family:'Orbitron',monospace;font-size:8px;letter-spacing:3px;color:rgba(245,197,24,.35);margin-bottom:6px}
.g2b{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:6px}
.btn{border:none;border-radius:10px;padding:12px 6px;font-family:'Orbitron',monospace;font-size:9px;font-weight:700;cursor:pointer;letter-spacing:1px;transition:.1s;width:100%}
.btn:active{transform:scale(.93)}
.bst{background:linear-gradient(135deg,#14532d,#166534);color:#4ade80;border:1px solid rgba(74,222,128,.2)}
.bsp{background:linear-gradient(135deg,#7f1d1d,#991b1b);color:#f87171;border:1px solid rgba(248,113,113,.2)}
.bln{background:rgba(34,197,94,.1);color:#22c55e;border:1px solid rgba(34,197,94,.18);font-size:8px;padding:10px 4px}
.bsh{background:rgba(239,68,68,.1);color:#ef4444;border:1px solid rgba(239,68,68,.18);font-size:8px;padding:10px 4px}
.bcl{background:rgba(245,197,24,.07);color:var(--g);border:1px solid rgba(245,197,24,.15);font-size:8px;padding:10px 4px}
.bca{background:rgba(168,85,247,.08);color:#c084fc;border:1px solid rgba(168,85,247,.2);font-size:8px;padding:10px}
.po{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.05);border-radius:10px;padding:9px 11px;margin-bottom:6px;position:relative;overflow:hidden}
.po.lg::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:#22c55e;box-shadow:0 0 5px #22c55e}
.po.sh::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:#ef4444;box-shadow:0 0 5px #ef4444}
.pt{display:flex;justify-content:space-between;align-items:center;margin-bottom:3px}
.py{font-family:'Orbitron',monospace;font-size:11px;font-weight:700}
.pd{font-size:8px;font-weight:700;letter-spacing:2px;padding:2px 6px;border-radius:20px}
.pd.lg{background:rgba(34,197,94,.12);color:#22c55e;border:1px solid rgba(34,197,94,.2)}
.pd.sh{background:rgba(239,68,68,.12);color:#ef4444;border:1px solid rgba(239,68,68,.2)}
.pr{display:flex;justify-content:space-between;font-size:10px;color:rgba(255,255,255,.32);margin-top:2px}
.pp{font-family:'Orbitron',monospace;font-size:12px;font-weight:900}
.tsl{display:flex;gap:5px;margin-top:3px}
.tpb{font-size:7px;padding:1px 5px;border-radius:20px;font-family:'Orbitron',monospace;background:rgba(34,197,94,.06);color:rgba(34,197,94,.55);border:1px solid rgba(34,197,94,.1)}
.slb{font-size:7px;padding:1px 5px;border-radius:20px;font-family:'Orbitron',monospace;background:rgba(239,68,68,.06);color:rgba(239,68,68,.55);border:1px solid rgba(239,68,68,.1)}
.np{text-align:center;padding:14px;color:rgba(255,255,255,.12);font-size:11px}
.toast{position:fixed;top:12px;left:50%;transform:translateX(-50%);padding:8px 16px;border-radius:20px;font-family:'Orbitron',monospace;font-size:9px;z-index:200;opacity:0;transition:.25s;pointer-events:none;white-space:nowrap}
.toast.ok{background:rgba(34,197,94,.15);border:1px solid rgba(34,197,94,.35);color:#4ade80}
.toast.er{background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.35);color:#f87171}
.toast.sv{opacity:1}
/* CHART */
.ctb{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap;align-items:center}
.sbt,.fbt{background:rgba(245,197,24,.06);border:1px solid rgba(245,197,24,.12);color:rgba(255,255,255,.5);padding:5px 10px;border-radius:8px;font-family:'Orbitron',monospace;font-size:8px;cursor:pointer}
.sbt.a,.fbt.a{background:rgba(245,197,24,.15);border-color:rgba(245,197,24,.4);color:var(--g)}
#chc{border-radius:12px;overflow:hidden;border:1px solid rgba(245,197,24,.1);height:350px}
.cif{display:flex;gap:12px;margin-top:6px;flex-wrap:wrap}
.cil{font-family:'Orbitron',monospace;font-size:9px;color:rgba(255,255,255,.3)}.cil b{color:var(--g)}
/* HISTORY */
.hss{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:10px}
.hsc{background:rgba(245,197,24,.04);border:1px solid rgba(245,197,24,.1);border-radius:10px;padding:9px 6px;text-align:center}
.hsn{font-family:'Orbitron',monospace;font-size:15px;font-weight:900;color:var(--g)}.hsl{font-size:8px;color:rgba(255,255,255,.25);margin-top:2px}
.hi{display:flex;justify-content:space-between;align-items:center;padding:8px 11px;border-bottom:1px solid rgba(255,255,255,.04)}
.his{font-size:11px;font-weight:600}.hid{font-size:8px;color:rgba(255,255,255,.2)}.hip{font-family:'Orbitron',monospace;font-size:11px;font-weight:700}
/* SETTINGS */
.sf{margin-bottom:14px}
.sf label{font-size:10px;color:rgba(255,255,255,.4);letter-spacing:2px;font-family:'Orbitron',monospace;display:block;margin-bottom:5px}
.sf input{width:100%;background:rgba(245,197,24,.04);border:1px solid rgba(245,197,24,.12);border-radius:8px;padding:10px 12px;color:#fff;font-family:'Rajdhani',sans-serif;font-size:14px;outline:none}
.sf input:focus{border-color:rgba(245,197,24,.35)}
.user-badge{background:rgba(245,197,24,.06);border:1px solid rgba(245,197,24,.15);border-radius:10px;padding:10px 14px;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center}
.rfb{height:2px;background:rgba(245,197,24,.06);margin:8px 0 4px;border-radius:1px;overflow:hidden}
.rfi{height:100%;background:var(--g);width:100%;transition:width 3s linear}
.ft{text-align:center;font-size:7px;color:rgba(255,255,255,.08);font-family:'Orbitron',monospace;letter-spacing:2px;padding-bottom:6px}
.logout{background:rgba(239,68,68,.07);border:1px solid rgba(239,68,68,.2);color:#f87171;border-radius:8px;padding:10px;width:100%;font-family:'Orbitron',monospace;font-size:9px;cursor:pointer;letter-spacing:1px;margin-top:10px}
</style></head><body>
<div id="toast" class="toast"></div>

<!-- PAGE 1: TRADE -->
<div id="p1" class="pg a">
<div class="logo">⚡ VANTAGE BOT</div>
<div class="sub">PAPER TRADING · LIVE</div>
<div class="sr"><div class="dot" id="d1"></div><span class="st" id="s1">Connexion...</span></div><hr>
<div class="g2">
  <div class="cd"><div class="cds">BTC/USD</div><div class="cdi">₿</div><div class="cdv" id="bp">--</div><div class="cdt" id="bt">--</div></div>
  <div class="cd"><div class="cds">XAU/USD</div><div class="cdi">🥇</div><div class="cdv" id="gp">--</div><div class="cdt" id="gt">--</div></div>
</div>
<div class="bal">
  <div><div class="blab">SOLDE DÉMO</div><div class="bval" id="bval">--</div></div>
  <div style="text-align:right">
    <div style="font-family:'Orbitron',monospace;font-size:8px;color:rgba(255,255,255,.25)">LEVIER</div>
    <div style="font-family:'Orbitron',monospace;font-size:18px;color:var(--g);font-weight:900" id="lv">x200</div>
    <div style="font-size:8px;color:rgba(255,255,255,.2)">x<span id="ms">10</span>€</div>
  </div>
</div>
<div class="g3">
  <div class="sc"><div class="sn" id="nt">0</div><div class="sl">TRADES</div></div>
  <div class="sc"><div class="sn" id="wr">--%</div><div class="sl">WIN RATE</div></div>
  <div class="sc"><div class="sn" id="tps">+0€</div><div class="sl">PROFIT</div></div>
</div><hr>
<div class="tt">⚡ CONTRÔLE</div>
<div class="g2b">
  <button class="btn bst" onclick="cmd('start')">▶ DÉMARRER<br><span style="font-size:7px;opacity:.5">Trading auto</span></button>
  <button class="btn bsp" onclick="cmd('stop')">⏹ ARRÊTER<br><span style="font-size:7px;opacity:.5">Stopper</span></button>
</div>
<div class="tt">📊 ORDRES MANUELS</div>
<div class="g2b">
  <button class="btn bln" onclick="cmd('buy_btc')">🟢 LONG BTC</button>
  <button class="btn bln" onclick="cmd('buy_gold')">🟢 LONG OR</button>
  <button class="btn bsh" onclick="cmd('sell_btc')">🔴 SHORT BTC</button>
  <button class="btn bsh" onclick="cmd('sell_gold')">🔴 SHORT OR</button>
  <button class="btn bcl" onclick="cmd('close_btc')">🔒 CLOSE BTC</button>
  <button class="btn bcl" onclick="cmd('close_gold')">🔒 CLOSE OR</button>
</div>
<button class="btn bca" onclick="cmd('closeall')" style="margin-bottom:8px">🔒 FERMER TOUTES LES POSITIONS</button>
<hr><div class="tt">⚡ POSITIONS OUVERTES</div>
<div id="pos"><div class="np">📭 Aucune position</div></div>
<div class="rfb"><div class="rfi" id="rfi"></div></div>
<div class="ft">VANTAGE PLATFORM · ZYPROZ · 2026</div>
</div>

<!-- PAGE 2: GRAPHIQUE -->
<div id="p2" class="pg">
<div class="logo" style="font-size:15px;padding:10px 0 4px">📈 GRAPHIQUE LIVE</div>
<div class="ctb">
  <button class="sbt a" id="sb-BTC" onclick="setSym('BTC')">₿ BTC</button>
  <button class="sbt" id="sb-GOLD" onclick="setSym('GOLD')">🥇 OR</button>
  <span style="flex:1"></span>
  <button class="fbt" id="fb-1m" onclick="setTf('1m')">1M</button>
  <button class="fbt a" id="fb-5m" onclick="setTf('5m')">5M</button>
  <button class="fbt" id="fb-15m" onclick="setTf('15m')">15M</button>
  <button class="fbt" id="fb-1h" onclick="setTf('1h')">1H</button>
</div>
<div id="chc"></div>
<div class="cif">
  <div class="cil">O:<b id="co">--</b></div><div class="cil">H:<b id="ch" class="gg">--</b></div>
  <div class="cil">L:<b id="cl" class="rr">--</b></div><div class="cil">C:<b id="cc">--</b></div>
</div>
<div class="ft" style="margin-top:8px">Binance · Auto-refresh 10s</div>
</div>

<!-- PAGE 3: HISTORIQUE -->
<div id="p3" class="pg">
<div class="logo" style="font-size:15px;padding:10px 0 4px">📋 HISTORIQUE</div>
<div class="hss">
  <div class="hsc"><div class="hsn" id="h-t">0</div><div class="hsl">TRADES</div></div>
  <div class="hsc"><div class="hsn gg" id="h-w">0</div><div class="hsl">GAGNANTS</div></div>
  <div class="hsc"><div class="hsn" id="h-p">+0€</div><div class="hsl">PROFIT NET</div></div>
</div>
<hr><div class="tt">📜 TRADES FERMÉS</div>
<div id="hl"><div class="np">Aucun trade fermé</div></div>
</div>

<!-- PAGE 4: PARAMÈTRES -->
<div id="p4" class="pg">
<div class="logo" style="font-size:15px;padding:10px 0 4px">⚙️ PARAMÈTRES</div>
<div class="user-badge">
  <div><div style="font-size:14px;font-weight:700" id="u-name">--</div><div style="font-size:10px;color:rgba(255,255,255,.35)" id="u-email">--</div></div>
  <div style="font-family:'Orbitron',monospace;font-size:10px;color:var(--g)">COMPTE ACTIF</div>
</div>
<hr><div class="tt">⚡ TRADING</div>
<div class="g2">
  <div class="sf"><label>LEVIER</label><input type="number" id="cfg-levier" value="200" min="1" max="500"></div>
  <div class="sf"><label>MISE (€)</label><input type="number" id="cfg-mise" value="10" min="1"></div>
</div>
<div class="g2">
  <div class="sf"><label>TAKE PROFIT %</label><input type="number" id="cfg-tp" value="1.0" step="0.1"></div>
  <div class="sf"><label>STOP LOSS %</label><input type="number" id="cfg-sl" value="0.3" step="0.1"></div>
</div>
<button class="btn bst" onclick="saveSettings()" style="margin-bottom:14px">💾 SAUVEGARDER</button>
<hr><div class="tt">🔗 CLÉ API VANTAGE (OPTIONNEL)</div>
<div class="sf"><label>META API TOKEN</label><input type="text" id="cfg-meta" placeholder="Colle ton token MetaAPI ici"></div>
<div class="sf"><label>ACCOUNT ID</label><input type="text" id="cfg-acid" placeholder="ID de ton compte Vantage"></div>
<button class="btn" onclick="saveApi()" style="background:rgba(245,197,24,.08);color:var(--g);border:1px solid rgba(245,197,24,.2);margin-bottom:8px">🔗 CONNECTER VANTAGE</button>
<div style="font-size:10px;color:rgba(255,255,255,.2);text-align:center;padding:6px">Les clés API permettent de trader en VRAI argent via Vantage Markets</div>
<hr>
<button class="logout" onclick="logout()">🚪 SE DÉCONNECTER</button>
<div class="rfb"><div class="rfi"></div></div>
<div class="ft">VANTAGE PLATFORM · ZYPROZ · 2026</div>
</div>

<nav class="bnav">
  <button class="bnt a" id="bn1" onclick="sp(1)">📊<span>TRADE</span></button>
  <button class="bnt" id="bn2" onclick="sp(2)">📈<span>GRAPH</span></button>
  <button class="bnt" id="bn3" onclick="sp(3)">📋<span>HISTORIQUE</span></button>
  <button class="bnt" id="bn4" onclick="sp(4)">⚙️<span>COMPTE</span></button>
</nav>

<script>
const TK=localStorage.getItem('vt');
if(!TK) window.location='/';
let cp=1;
function sp(n){document.querySelectorAll('.pg').forEach(p=>p.classList.remove('a'));document.querySelectorAll('.bnt').forEach(b=>b.classList.remove('a'));document.getElementById('p'+n).classList.add('a');document.getElementById('bn'+n).classList.add('a');cp=n;if(n===2)lc();if(n===3)rf3();if(n===4)loadSettings();}
const H={'Content-Type':'application/json','Authorization':'Bearer '+TK};
const ff=n=>n>=1000?n.toLocaleString('fr-FR',{maximumFractionDigits:2}):n.toFixed(2);
const pc=v=>v>=0?'gg':'rr';const ps=v=>v>=0?'+':'';
function toast(m,ok=true){const t=document.getElementById('toast');t.textContent=m;t.className='toast '+(ok?'ok':'er')+' sv';setTimeout(()=>t.classList.remove('sv'),2500);}
async function cmd(c){
  try{const r=await fetch('/api/cmd',{method:'POST',headers:H,body:JSON.stringify({cmd:c})});
  const d=await r.json();
  if(d.redirect){window.location=d.redirect;return;}
  toast(d.msg||(d.ok?'OK':'ERR'),d.ok);setTimeout(rf,400);}
  catch(e){toast('Connexion',false);}
}
async function rf(){
  try{
    const r=await fetch('/api/status',{headers:H});
    if(r.status===401){window.location='/';return;}
    const d=await r.json();
    document.getElementById('d1').className='dot '+(d.actif?'on':'off');
    document.getElementById('s1').textContent=d.actif?'🟢 BOT ACTIF — Trading en cours':'🔴 BOT ARRÊTÉ';
    if(d.btc){document.getElementById('bp').textContent='$'+ff(d.btc);document.getElementById('bt').textContent='⏱ '+new Date().toLocaleTimeString('fr-FR');}
    if(d.gold){document.getElementById('gp').textContent='$'+ff(d.gold);document.getElementById('gt').textContent='⏱ '+new Date().toLocaleTimeString('fr-FR');}
    document.getElementById('bval').textContent=ff(d.balance)+'€';
    document.getElementById('lv').textContent='x'+d.levier;document.getElementById('ms').textContent=d.mise;
    const h=d.trades||[];const w=h.filter(t=>(t.pnl||0)>0).length;const tp=h.reduce((s,t)=>s+(t.pnl||0),0);
    document.getElementById('nt').textContent=h.length;
    const we=document.getElementById('wr');we.textContent=h.length?Math.round(w/h.length*100)+'%':'--%';we.className='sn '+(h.length&&w/h.length>=0.5?'gg':'rr');
    const te=document.getElementById('tps');te.textContent=ps(tp)+tp.toFixed(2)+'€';te.className='sn '+pc(tp);
    const pos=d.positions||{};const ks=Object.keys(pos);const pE=document.getElementById('pos');
    if(!ks.length){pE.innerHTML='<div class="np">📭 Aucune position — en attente de signal</div>';}
    else{pE.innerHTML=ks.map(sym=>{
      const p=pos[sym];const cpx=sym==='BTC'?d.btc:d.gold;const e=parseFloat(p.e);
      const pnl=p.d==='BUY'?parseFloat(p.v)*(cpx-e):parseFloat(p.v)*(e-cpx);
      const pct=p.d==='BUY'?(cpx-e)/e*100:(e-cpx)/e*100;
      const dir=p.d==='BUY'?'lg':'sh';const ic=sym==='BTC'?'₿':'🥇';
      return`<div class="po ${dir}"><div class="pt"><div class="py">${ic} ${sym}</div><div class="pd ${dir}">${p.d==='BUY'?'⬆ LONG':'⬇ SHORT'}</div></div>
      <div class="pr"><span>Entrée <b style="color:#fff">${e.toFixed(2)}$</b></span><span>Actuel <b style="color:var(--g)">${cpx?cpx.toFixed(2)+'$':'--'}</b></span></div>
      <div class="pr" style="margin-top:3px"><span>Vol:${p.v}</span><span class="pp ${pc(pnl)}">${ps(pnl)}${Math.abs(pnl).toFixed(4)}€ (${ps(pct)}${Math.abs(pct).toFixed(2)}%)</span></div>
      <div class="tsl"><span class="tpb">TP ${parseFloat(p.tp).toFixed(2)}$</span><span class="slb">SL ${parseFloat(p.sl).toFixed(2)}$</span></div></div>`;
    }).join('');}
    document.getElementById('rfi').style.transition='none';document.getElementById('rfi').style.width='100%';
    setTimeout(()=>{document.getElementById('rfi').style.transition='width 3s linear';document.getElementById('rfi').style.width='0%';},50);
    if(cp===3)uh(h);
  }catch(e){}
}
function uh(h){
  const w=h.filter(t=>(t.pnl||0)>0).length;const tp=h.reduce((s,t)=>s+(t.pnl||0),0);
  document.getElementById('h-t').textContent=h.length;
  const we=document.getElementById('h-w');we.textContent=w;we.className='hsn '+(w>0?'gg':'');
  const pe=document.getElementById('h-p');pe.textContent=ps(tp)+tp.toFixed(4)+'€';pe.className='hsn '+pc(tp);
  const le=document.getElementById('hl');
  if(!h.length){le.innerHTML='<div class="np">Aucun trade fermé</div>';return;}
  le.innerHTML=h.map(t=>{
    const ic=t.s==='BTC'?'₿':'🥇';const dt=t.ts?new Date(t.ts).toLocaleTimeString('fr-FR'):'';
    return`<div class="hi"><div><div class="his">${ic} ${t.s} ${t.d==='BUY'?'🟢 LONG':'🔴 SHORT'}</div>
    <div class="hid">${t.r||''} · ${dt}</div>
    <div class="hid">Entrée ${(t.e||0).toFixed(2)}$ → ${(t.x||0).toFixed(2)}$</div></div>
    <div class="hip ${pc(t.pnl||0)}">${ps(t.pnl||0)}${Math.abs(t.pnl||0).toFixed(4)}€</div></div>`;
  }).join('');
}
async function rf3(){try{const d=await fetch('/api/status',{headers:H}).then(r=>r.json());uh(d.trades||[]);}catch(e){}}
async function loadSettings(){
  try{const d=await fetch('/api/me',{headers:H}).then(r=>r.json());
  if(!d.ok){window.location='/';return;}
  document.getElementById('u-name').textContent=d.user.username;
  document.getElementById('u-email').textContent=d.user.email;
  document.getElementById('cfg-levier').value=d.user.levier;
  document.getElementById('cfg-mise').value=d.user.mise;
  document.getElementById('cfg-tp').value=d.user.tp;
  document.getElementById('cfg-sl').value=d.user.sl;
  document.getElementById('cfg-meta').value=d.user.meta_token||'';
  document.getElementById('cfg-acid').value=d.user.account_id||'';}catch(e){}
}
async function saveSettings(){
  const body={levier:parseInt(document.getElementById('cfg-levier').value),mise:parseFloat(document.getElementById('cfg-mise').value),tp:parseFloat(document.getElementById('cfg-tp').value),sl:parseFloat(document.getElementById('cfg-sl').value)};
  const r=await fetch('/api/settings',{method:'POST',headers:H,body:JSON.stringify(body)});
  const d=await r.json();toast(d.msg||(d.ok?'✅ Sauvegardé':'❌'),d.ok);
}
async function saveApi(){
  const body={meta_token:document.getElementById('cfg-meta').value,account_id:document.getElementById('cfg-acid').value};
  const r=await fetch('/api/apikeys',{method:'POST',headers:H,body:JSON.stringify(body)});
  const d=await r.json();toast(d.msg||(d.ok?'✅ Clés sauvegardées':'❌'),d.ok);
}
function logout(){localStorage.removeItem('vt');window.location='/';}
let chart=null,cs=null,cS='BTC',cT='5m';
function setSym(s){cS=s;['BTC','GOLD'].forEach(x=>document.getElementById('sb-'+x).classList.toggle('a',x===s));lc();}
function setTf(tf){cT=tf;['1m','5m','15m','1h'].forEach(x=>document.getElementById('fb-'+x).classList.toggle('a',x===tf));lc();}
function lc(){
  const con=document.getElementById('chc');
  if(!chart){
    chart=LightweightCharts.createChart(con,{width:con.clientWidth,height:350,layout:{background:{color:'#07070a'},textColor:'rgba(255,255,255,0.35)'},grid:{vertLines:{color:'rgba(245,197,24,0.04)'},horzLines:{color:'rgba(245,197,24,0.04)'}},crosshair:{mode:LightweightCharts.CrosshairMode.Normal},rightPriceScale:{borderColor:'rgba(245,197,24,0.1)'},timeScale:{borderColor:'rgba(245,197,24,0.1)',timeVisible:true,secondsVisible:false}});
    cs=chart.addCandlestickSeries({upColor:'#22c55e',downColor:'#ef4444',borderUpColor:'#22c55e',borderDownColor:'#ef4444',wickUpColor:'#22c55e',wickDownColor:'#ef4444'});
    chart.subscribeCrosshairMove(p=>{if(p.seriesData&&p.seriesData.size>0){const cd=p.seriesData.values().next().value;if(cd){document.getElementById('co').textContent='$'+cd.open.toFixed(2);document.getElementById('ch').textContent='$'+cd.high.toFixed(2);document.getElementById('cl').textContent='$'+cd.low.toFixed(2);document.getElementById('cc').textContent='$'+cd.close.toFixed(2);}}});
  }
  fetch('/api/ohlc?s='+cS+'&tf='+cT,{headers:H}).then(r=>r.json()).then(data=>{
    if(data&&data.length){cs.setData(data.map(c=>({time:c.t,open:c.o,high:c.h,low:c.l,close:c.c})));chart.timeScale().fitContent();const last=data[data.length-1];document.getElementById('co').textContent='$'+last.o.toFixed(2);document.getElementById('ch').textContent='$'+last.h.toFixed(2);document.getElementById('cl').textContent='$'+last.l.toFixed(2);document.getElementById('cc').textContent='$'+last.c.toFixed(2);}
  }).catch(()=>{});
}
rf();setInterval(()=>{if(cp===1||cp===3)rf();},3000);setInterval(()=>{if(cp===2)lc();},10000);
</script></body></html>"""

# ══════════════════════════════════════════════════════════════
#   HTTP SERVER (API + HTML)
# ══════════════════════════════════════════════════════════════
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a): pass

    def send_json(self,data,code=200):
        b=json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers(); self.wfile.write(b)

    def send_html(self,html):
        b=html.encode()
        self.send_response(200)
        self.send_header("Content-Type","text/html;charset=utf-8")
        self.end_headers(); self.wfile.write(b)

    def get_token(self):
        auth=self.headers.get("Authorization","")
        return auth.replace("Bearer ","") if auth.startswith("Bearer ") else None

    def do_HEAD(self):
        """UptimeRobot envoie HEAD - répondre OK"""
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
        path = self.path.split("?")[0]
        if path == "/" or path == "/login":
            self.send_html(LOGIN_HTML)
        elif path == "/dashboard":
            self.send_html(DASHBOARD_HTML)
        elif path == "/api/me":
            u = auth_user(self.get_token())
            if not u: self.send_json({"ok":False,"error":"Non authentifié"},401); return
            self.send_json({"ok":True,"user":{"username":u["username"],"email":u["email"],"levier":u["levier"],"mise":u["mise"],"tp":u["tp"],"sl":u["sl"],"meta_token":u["meta_token"],"account_id":u["account_id"],"balance":u["balance"]}})
        elif path == "/api/status":
            u = auth_user(self.get_token())
            if not u: self.send_json({"ok":False},401); return
            pos = get_positions(u["id"])
            trades = get_trades(u["id"])
            self.send_json({
                "ok": True, "actif": bool(u["bot_actif"]),
                "balance": round(u["balance"],2),
                "levier": u["levier"], "mise": u["mise"],
                "btc": round(get_btc(),2), "gold": round(get_gold(),2),
                "positions": pos, "trades": trades
            })
        elif path == "/ping" or path == "/health":
            self.send_response(200)
            self.send_header("Content-Type","text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        elif path == "/api/ohlc":
            qs = parse_qs(urlparse(self.path).query)
            u = auth_user(self.get_token())
            if not u: self.send_json([],401); return
            data = get_ohlc(qs.get("s",["BTC"])[0], qs.get("tf",["5m"])[0])
            self.send_json(data)
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length",0))
        body = json.loads(self.rfile.read(n)) if n else {}
        path = self.path

        if path == "/api/register":
            email=body.get("email","").lower().strip()
            username=body.get("username","").strip()
            password=body.get("password","")
            if not email or not username or len(password)<6:
                self.send_json({"ok":False,"error":"Données invalides"}); return
            try:
                token=gen_token()
                db=get_db()
                db.execute("INSERT INTO users (email,username,password_hash,token) VALUES (?,?,?,?)",
                           (email,username,hash_pw(password),token))
                db.commit(); db.close()
                self.send_json({"ok":True,"token":token})
            except sqlite3.IntegrityError:
                self.send_json({"ok":False,"error":"Email déjà utilisé"})

        elif path == "/api/login":
            email=body.get("email","").lower().strip()
            pw=body.get("password","")
            db=get_db()
            u=db.execute("SELECT * FROM users WHERE email=? AND password_hash=?",(email,hash_pw(pw))).fetchone()
            if u:
                token=gen_token()
                db.execute("UPDATE users SET token=? WHERE id=?",(token,u["id"]))
                db.commit(); db.close()
                self.send_json({"ok":True,"token":token})
            else:
                db.close(); self.send_json({"ok":False,"error":"Email ou mot de passe incorrect"})

        elif path == "/api/settings":
            u=auth_user(self.get_token())
            if not u: self.send_json({"ok":False},401); return
            levier=int(body.get("levier",200)); mise=float(body.get("mise",10))
            tp=float(body.get("tp",1.0)); sl=float(body.get("sl",0.3))
            db=get_db()
            db.execute("UPDATE users SET levier=?,mise=?,tp=?,sl=? WHERE id=?",(levier,mise,tp,sl,u["id"]))
            db.commit(); db.close()
            self.send_json({"ok":True,"msg":"✅ Paramètres sauvegardés"})

        elif path == "/api/apikeys":
            u=auth_user(self.get_token())
            if not u: self.send_json({"ok":False},401); return
            meta=body.get("meta_token",""); acid=body.get("account_id","")
            db=get_db()
            db.execute("UPDATE users SET meta_token=?,account_id=? WHERE id=?",(meta,acid,u["id"]))
            db.commit(); db.close()
            self.send_json({"ok":True,"msg":"✅ Clés API sauvegardées"})

        elif path == "/api/cmd":
            u=auth_user(self.get_token())
            if not u: self.send_json({"ok":False,"redirect":"/"},401); return
            c=body.get("cmd",""); uid=u["id"]
            ok=True; msg=""

            if c=="start":
                db=get_db(); db.execute("UPDATE users SET bot_actif=1 WHERE id=?",(uid,)); db.commit(); db.close()
                ensure_trading_thread(uid)
                msg=f"🟢 Bot démarré ! x{u['levier']} | {u['mise']}€"
                tg_send(f"🚀 *Bot démarré* — {u['username']}\nx{u['levier']} | {u['mise']}€ | Solde `{u['balance']:.2f}€`")
            elif c=="stop":
                db=get_db(); db.execute("UPDATE users SET bot_actif=0 WHERE id=?",(uid,)); db.commit(); db.close()
                msg="⏹ Bot arrêté"
            elif c in("buy_btc","buy_gold","sell_btc","sell_gold"):
                sym="BTC" if "btc" in c else "GOLD"; d="BUY" if "buy" in c else "SELL"
                price=px(sym)
                if price:
                    t=open_trade(uid,sym,d,price)
                    if t:
                        msg=f"{'🟢 LONG' if d=='BUY' else '🔴 SHORT'} {'₿ BTC' if sym=='BTC' else '🥇 OR'} @ {price:.2f}$"
                        tg_send(f"⚡ *{msg}*\n`{u['mise']}€`×x{u['levier']}=`{u['mise']*u['levier']}€`")
                    else: ok=False; msg="❌ Solde insuffisant"
                else: ok=False; msg="❌ Prix indisponible"
            elif c in("close_btc","close_gold"):
                sym="BTC" if "btc" in c else "GOLD"
                price=px(sym)
                pnl=close_trade(uid,sym,price,"Fermeture manuelle")
                if pnl is not None:
                    u2=get_user_cfg(uid)
                    msg=f"🔒 {sym} fermé | {pnl:+.4f}€ | Solde: {u2['balance']:.2f}€"
                    tg_send(f"🔒 *{sym} fermé manuellement* | `{pnl:+.4f}€` | Solde:`{u2['balance']:.2f}€`")
                else: ok=False; msg=f"Pas de position {sym}"
            elif c=="closeall":
                pos=get_positions(uid); tot=0
                for sym in list(pos.keys()):
                    price=px(sym) or pos[sym]["e"]
                    pnl=close_trade(uid,sym,float(price),"Fermer tout")
                    if pnl: tot+=pnl
                if pos: msg=f"🔒 Tout fermé | {tot:+.4f}€"
                else: ok=False; msg="Rien à fermer"

            self.send_json({"ok":ok,"msg":msg})
        else:
            self.send_response(404); self.end_headers()

def run_server():
    import socket as sk
    class S(HTTPServer):
        allow_reuse_address=True
        def server_bind(self): self.socket.setsockopt(sk.SOL_SOCKET,sk.SO_REUSEADDR,1);super().server_bind()
    s=S(("0.0.0.0",PORT),Handler)
    print(f"✅ Vantage Platform sur port {PORT}")
    s.serve_forever()

if __name__=="__main__":
    init_db()
    print(f"⚡ VANTAGE PLATFORM — Démarrage sur port {PORT}")
    print(f"   DB: {DB_PATH}")
    run_server()
