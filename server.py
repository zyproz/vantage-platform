#!/usr/bin/env python3
"""ZYCRYPTO PLATFORM v1.2 — Multi-crypto + Cloud Gist + Auth fix"""
import json, os, hashlib, secrets, time, threading, requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT        = int(os.environ.get("PORT", 8000))
SECRET_KEY  = os.environ.get("SECRET_KEY", "zyproz-zycrypto-2026-xK9mP2qR")
TG_TOKEN    = os.environ.get("TG_TOKEN", "8858889412:AAElLpyQCIqw3PIYeAJtxeH56DQgXBUn6Ls")
TG_ADMIN_ID = int(os.environ.get("TG_ADMIN", "5354522228"))
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "ugo.scule@gmail.com").lower()
GH_TOKEN    = os.environ.get("GH_TOKEN", "")
GIST_ID     = os.environ.get("GIST_ID", "")

# ── Symboles supportés ────────────────────────────────────────
SYMBOLS = {
    "BTC":  {"name":"Bitcoin",      "icon":"₿",  "pair":"BTCUSDT",  "color":"#f5c518"},
    "ETH":  {"name":"Ethereum",     "icon":"Ξ",  "pair":"ETHUSDT",  "color":"#627eea"},
    "BNB":  {"name":"BNB",          "icon":"◈",  "pair":"BNBUSDT",  "color":"#f3ba2f"},
    "SOL":  {"name":"Solana",       "icon":"◎",  "pair":"SOLUSDT",  "color":"#9945ff"},
    "XRP":  {"name":"Ripple",       "icon":"✕",  "pair":"XRPUSDT",  "color":"#00aae4"},
    "DOGE": {"name":"Dogecoin",     "icon":"Ð",  "pair":"DOGEUSDT", "color":"#c2a633"},
    "GOLD": {"name":"Or",           "icon":"🥇", "pair":"PAXGUSDT", "color":"#ffd700"},
}

# ══════════════════════════════════════════════════════════════
#   GIST DATABASE
# ══════════════════════════════════════════════════════════════
class RepoDB:
    """Base de données stockée dans un repo GitHub privé (scope: repo)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._data = {"users":{}, "positions":{}, "trades":{}}
        self._dirty = False
        self._saving = False
        self.db_repo = os.environ.get("DB_REPO", "zycrypto-db")

    def _gh(self):
        return {"Authorization":f"token {GH_TOKEN}",
                "Content-Type":"application/json",
                "Accept":"application/vnd.github.v3+json"}

    def _get_file(self, fname):
        url = f"https://api.github.com/repos/{os.environ.get('DB_OWNER','')}/{self.db_repo}/contents/{fname}"
        r = requests.get(url, headers=self._gh(), timeout=10)
        if r.status_code == 200:
            import base64 as b64
            content = b64.b64decode(r.json()["content"]).decode()
            return json.loads(content), r.json()["sha"]
        return None, None

    def _put_file(self, fname, data, sha=None):
        import base64 as b64
        url = f"https://api.github.com/repos/{os.environ.get('DB_OWNER','')}/{self.db_repo}/contents/{fname}"
        body = {
            "message": f"db: update {fname}",
            "content": b64.b64encode(json.dumps(data).encode()).decode(),
        }
        if sha: body["sha"] = sha
        r = requests.put(url, headers=self._gh(), json=body, timeout=15)
        return r.status_code in (200, 201)

    def load(self):
        if not GH_TOKEN:
            print("  Pas de GH_TOKEN - donnees en memoire"); return
        try:
            for n in ["users","positions","trades"]:
                data, _ = self._get_file(f"{n}.json")
                if data is not None:
                    self._data[n] = data
            u = len(self._data["users"])
            t = sum(len(v) for v in self._data["trades"].values())
            print(f"  OK DB chargee - {u} users, {t} trades")
        except Exception as e:
            print(f"  Erreur DB: {e}")

    def save(self, force=False):
        if not GH_TOKEN: return
        if not self._dirty and not force: return
        if self._saving: return
        self._saving = True
        try:
            for n in ["users","positions","trades"]:
                _, sha = self._get_file(f"{n}.json")
                self._put_file(f"{n}.json", self._data[n], sha)
            self._dirty = False
        except: pass
        finally: self._saving = False

    def _save_bg(self): threading.Thread(target=self.save,daemon=True).start()

    def get_by_email(self, email):
        email=email.lower()
        with self._lock:
            for u in self._data["users"].values():
                if u.get("email","").lower()==email: return dict(u)
        return None

    def get_by_token(self, token):
        with self._lock:
            for u in self._data["users"].values():
                if u.get("token")==token: return dict(u)
        return None

    def get_by_id(self, uid):
        with self._lock:
            u=self._data["users"].get(uid)
            return dict(u) if u else None

    def create_user(self, email, username, pw_hash, token, is_admin=False):
        uid = secrets.token_hex(16)
        with self._lock:
            for u in self._data["users"].values():
                if u.get("email","").lower()==email.lower(): return None
            user = {"id":uid,"email":email.lower(),"username":username,
                    "password_hash":pw_hash,"token":token,"balance":1000.0,
                    "levier":200,"mise":10.0,"tp":1.0,"sl":0.3,"interval":5,
                    "bot_actif":False,"is_admin":is_admin,
                    "meta_token":"","account_id":"","symbols":["BTC","ETH"]}
            self._data["users"][uid]=user
            self._dirty=True
        self.save()
        return dict(user)

    def update_user(self, uid, data):
        with self._lock:
            if uid in self._data["users"]:
                self._data["users"][uid].update(data)
                self._dirty=True
        self._save_bg()

    def update_token(self, email, token):
        with self._lock:
            for u in self._data["users"].values():
                if u.get("email","").lower()==email.lower():
                    u["token"]=token; self._dirty=True; break
        self.save()

    def get_all_active(self):
        with self._lock:
            return [dict(u) for u in self._data["users"].values() if u.get("bot_actif")]

    def get_admin(self):
        with self._lock:
            for u in self._data["users"].values():
                if u.get("is_admin"): return dict(u)
        return None

    def get_positions(self, uid):
        with self._lock: return dict(self._data["positions"].get(uid,{}))

    def save_position(self, uid, sym, d, e, v, tp, sl, m):
        with self._lock:
            if uid not in self._data["positions"]: self._data["positions"][uid]={}
            self._data["positions"][uid][sym]={"d":d,"e":e,"v":v,"tp":tp,"sl":sl,"m":m,"ts":_now()}
            self._dirty=True
        self._save_bg()

    def del_position(self, uid, sym):
        with self._lock:
            if uid in self._data["positions"] and sym in self._data["positions"][uid]:
                del self._data["positions"][uid][sym]; self._dirty=True
        self._save_bg()

    def get_trades(self, uid, limit=100):
        with self._lock:
            t=self._data["trades"].get(uid,[])
            return list(reversed(t[-limit:]))

    def save_trade(self, uid, sym, d, e, x, v, pnl, reason):
        with self._lock:
            if uid not in self._data["trades"]: self._data["trades"][uid]=[]
            self._data["trades"][uid].append({"ts":_now(),"s":sym,"d":d,"e":e,"x":x,"v":v,"pnl":pnl,"r":reason})
            self._dirty=True
        self._save_bg()

DB = RepoDB()

# ══════════════════════════════════════════════════════════════
#   AUTH
# ══════════════════════════════════════════════════════════════
def hp(pw): return hashlib.sha256((pw+SECRET_KEY).encode()).hexdigest()
def gt():   return secrets.token_urlsafe(32)
def au(tk): return DB.get_by_token(tk) if tk else None
def get_tok(h): a=h.get("Authorization",""); return a[7:] if a.startswith("Bearer ") else None

# ══════════════════════════════════════════════════════════════
#   PRIX
# ══════════════════════════════════════════════════════════════
_pc={}; _pt={}

def get_price(sym):
    if sym in _pc and time.time()-_pt.get(sym,0)<5: return _pc[sym]
    try:
        pair = SYMBOLS[sym]["pair"]
        v = float(requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={pair}",timeout=5).json()["price"])
        _pc[sym]=v; _pt[sym]=time.time(); return v
    except: return _pc.get(sym,0)

def get_all_prices():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price",timeout=8).json()
        pairs = {s["symbol"]:float(s["price"]) for s in r}
        result = {}
        for sym,info in SYMBOLS.items():
            p = pairs.get(info["pair"],0)
            if p: _pc[sym]=p; _pt[sym]=time.time(); result[sym]=p
        return result
    except:
        return {sym:get_price(sym) for sym in SYMBOLS}

def candles(sym, n=70):
    try:
        pair = SYMBOLS[sym]["pair"]
        r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={pair}&interval=5m&limit={n}",timeout=10)
        return [float(k[4]) for k in r.json()]
    except: return [get_price(sym) or 100]*n

def rsi(c,p=14):
    if len(c)<p+1: return 50.0
    g,l=[],[]
    for i in range(1,len(c)): d=c[i]-c[i-1]; g.append(max(d,0)); l.append(max(-d,0))
    ag=sum(g[:p])/p; al=sum(l[:p])/p
    for i in range(p,len(g)): ag=(ag*(p-1)+g[i])/p; al=(al*(p-1)+l[i])/p
    return 100-(100/(1+ag/al)) if al else 100.0

def ma(c,p): return sum(c[-p:])/p if len(c)>=p else c[-1]

def get_signal(sym):
    cl=candles(sym); p=get_price(sym) or cl[-1]; r=rsi(cl)
    maf=ma(cl,5); mas=ma(cl,13); pr=cl[:-1]
    bull=(ma(pr,5)<=ma(pr,13))and(maf>mas)
    bear=(ma(pr,5)>=ma(pr,13))and(maf<mas)
    if r<40 and bull: return "BUY",p,round(r,1)
    if r>60 and bear: return "SELL",p,round(r,1)
    return None,p,round(r,1)

def calc_pnl(d,e,v,cp): return round(float(v)*(float(cp)-float(e)),4) if d=="BUY" else round(float(v)*(float(e)-float(cp)),4)

def get_ohlc(sym,tf="5m",limit=100):
    try:
        pair=SYMBOLS.get(sym,{}).get("pair","BTCUSDT")
        r=requests.get(f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={tf}&limit={limit}",timeout=10)
        return [{"t":int(k[0])/1000,"o":float(k[1]),"h":float(k[2]),"l":float(k[3]),"c":float(k[4])} for k in r.json()]
    except: return []

# ══════════════════════════════════════════════════════════════
#   TRADING ENGINE
# ══════════════════════════════════════════════════════════════
_threads={}

def tg(msg):
    try: requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",json={"chat_id":TG_ADMIN_ID,"text":msg,"parse_mode":"Markdown"},timeout=8)
    except: pass

def open_trade(uid, sym, direction, price):
    u=DB.get_by_id(uid)
    if not u or float(u["balance"])<float(u["mise"]): return None
    mise=float(u["mise"]); lev=int(u["levier"])
    tp_p=float(u["tp"])/100; sl_p=float(u["sl"])/100
    vol=max(round((mise*lev/price)/0.0001)*0.0001,0.0001)
    tp=round(price*(1+tp_p),6) if direction=="BUY" else round(price*(1-tp_p),6)
    sl=round(price*(1-sl_p),6) if direction=="BUY" else round(price*(1+sl_p),6)
    DB.update_user(uid,{"balance":round(float(u["balance"])-mise,4)})
    DB.save_position(uid,sym,direction,price,vol,tp,sl,mise)
    return {"v":vol,"tp":tp,"sl":sl,"m":mise}

def close_trade(uid, sym, cp, reason):
    pos=DB.get_positions(uid)
    if sym not in pos: return None
    p=pos[sym]; pnl=calc_pnl(p["d"],p["e"],p["v"],cp)
    u=DB.get_by_id(uid)
    DB.update_user(uid,{"balance":round(float(u["balance"])+float(p["m"])+pnl,4)})
    DB.save_trade(uid,sym,p["d"],float(p["e"]),float(cp),float(p["v"]),pnl,reason)
    DB.del_position(uid,sym)
    return pnl

def trading_loop(uid):
    tour=0
    while True:
        u=DB.get_by_id(uid)
        if not u or not u.get("bot_actif"): time.sleep(2); continue
        syms=u.get("symbols",["BTC","ETH"])
        for sym in syms:
            u=DB.get_by_id(uid)
            if not u or not u.get("bot_actif"): break
            if sym not in SYMBOLS: continue
            try:
                sn,price,rv=get_signal(sym); pos=DB.get_positions(uid); en=sym in pos
                if en:
                    p=pos[sym]; d=p["d"]; r=None
                    # BOT: seulement TP/SL — pas de retournement sur positions manuelles
                    if d=="BUY":
                        if price>=float(p["tp"]): r="✅ Take-Profit"
                        elif price<=float(p["sl"]): r="🛡️ Stop-Loss"
                    else:
                        if price<=float(p["tp"]): r="✅ Take-Profit"
                        elif price>=float(p["sl"]): r="🛡️ Stop-Loss"
                    if r:
                        pnl=close_trade(uid,sym,price,r)
                        if pnl is not None:
                            u2=DB.get_by_id(uid); nm=SYMBOLS[sym]["name"]; ic=SYMBOLS[sym]["icon"]
                            tg(f"{'💰' if pnl>=0 else '💸'} *{ic} {nm}* — {r}\n`{float(p['e']):.4f}` → `{price:.4f}`\nProfit:`{pnl:+.4f}€` Solde:`{u2['balance']:.2f}€`")
                        en=False
                # BOT: n'ouvre de nouvelles positions QUE si aucune position sur ce symbole
                if not en and sn in("BUY","SELL"):
                    u=DB.get_by_id(uid)
                    if u and float(u["balance"])>=float(u["mise"]):
                        t=open_trade(uid,sym,sn,price)
                        if t:
                            nm=SYMBOLS[sym]["name"]; ic=SYMBOLS[sym]["icon"]
                            tg(f"⚡ *{'🟢 LONG' if sn=='BUY' else '🔴 SHORT'}* {ic} {nm}\n`{price:.4f}$` RSI:`{rv}` TP:`{t['tp']:.4f}$`")
            except: pass
            time.sleep(0.3)
        if tour%120==0 and tour>0:
            pos2=DB.get_positions(uid)
            if pos2:
                msg="📡 *Positions:*\n"
                for sk,p in pos2.items():
                    cp=get_price(sk); pnl2=calc_pnl(p["d"],p["e"],p["v"],cp) if cp else 0
                    msg+=f"  {SYMBOLS[sk]['icon']} {sk} `{pnl2:+.4f}€`\n"
                tg(msg)
        tour+=1; u=DB.get_by_id(uid); time.sleep(float(u["interval"]) if u else 5)

def ensure_thread(uid):
    if uid not in _threads or not _threads[uid].is_alive():
        t=threading.Thread(target=trading_loop,args=(uid,),daemon=True); t.start(); _threads[uid]=t

def start_all(): [ensure_thread(u["id"]) for u in DB.get_all_active()]

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
.sub{font-family:'Orbitron',monospace;font-size:7px;letter-spacing:7px;color:rgba(245,197,24,.3);text-align:center;margin-bottom:5px}
.ver{font-family:'Orbitron',monospace;font-size:7px;color:rgba(255,255,255,.1);text-align:center;margin-bottom:22px}
.tabs{display:flex;margin-bottom:20px;border-bottom:1px solid rgba(245,197,24,.12)}
.tab{flex:1;padding:10px;background:none;border:none;color:rgba(255,255,255,.3);font-family:'Orbitron',monospace;font-size:9px;letter-spacing:2px;cursor:pointer}
.tab.a{color:#f5c518;border-bottom:2px solid #f5c518}
.form{display:none}.form.a{display:block}
.f{margin-bottom:13px}
.f label{font-size:9px;color:rgba(255,255,255,.35);letter-spacing:2px;font-family:'Orbitron',monospace;display:block;margin-bottom:5px}
.f input{width:100%;background:rgba(245,197,24,.04);border:1px solid rgba(245,197,24,.12);border-radius:10px;padding:12px 14px;color:#fff;font-family:'Rajdhani',sans-serif;font-size:15px;outline:none;transition:.2s}
.f input:focus{border-color:rgba(245,197,24,.35);background:rgba(245,197,24,.06)}
.btn{width:100%;padding:14px;background:linear-gradient(135deg,rgba(245,197,24,.1),rgba(245,197,24,.2));border:1px solid rgba(245,197,24,.35);border-radius:12px;color:#f5c518;font-family:'Orbitron',monospace;font-size:10px;font-weight:700;letter-spacing:2px;cursor:pointer;transition:.15s;margin-top:4px}
.btn:active{transform:scale(.98)}
.msg{text-align:center;padding:10px;border-radius:8px;font-size:12px;margin-top:10px;display:none}
.msg.ok{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.25);color:#4ade80}
.msg.er{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.25);color:#f87171}
.div{height:1px;background:linear-gradient(90deg,transparent,rgba(245,197,24,.18),transparent);margin:20px 0}
.tag{text-align:center;font-size:9px;color:rgba(255,255,255,.15);font-family:'Orbitron',monospace;letter-spacing:1px}
.cryptos{display:flex;justify-content:center;gap:8px;flex-wrap:wrap;margin-bottom:18px}
.cr{font-family:'Orbitron',monospace;font-size:8px;padding:3px 8px;border-radius:20px;border:1px solid rgba(245,197,24,.12);color:rgba(245,197,24,.4)}
</style></head><body>
<div class="box">
  <div class="logo">⚡ ZYCRYPTO</div>
  <div class="sub">TRADING PLATFORM</div>
  <div class="ver">v1.2 — MULTI-CRYPTO · CLOUD</div>
  <div class="cryptos">
    <span class="cr">₿ BTC</span><span class="cr">Ξ ETH</span><span class="cr">◈ BNB</span>
    <span class="cr">◎ SOL</span><span class="cr">✕ XRP</span><span class="cr">🥇 OR</span>
  </div>
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
  <div class="div"></div>
  <div class="tag">₿ Bitcoin · Ξ Ethereum · ◎ Solana · 🥇 Or</div>
</div>
<script>
function sw(n){document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('a',i===n));document.querySelectorAll('.form').forEach((f,i)=>f.classList.toggle('a',i===n));}
function msg(id,t,ok){const e=document.getElementById(id);e.textContent=t;e.className='msg '+(ok?'ok':'er');e.style.display='block';}
async function login(){
  const e=document.getElementById('le').value.trim(),p=document.getElementById('lp').value;
  if(!e||!p){msg('lm','Remplis tous les champs',false);return;}
  const btn=document.querySelector('#f0 .btn');btn.textContent='Connexion...';btn.disabled=true;
  try{
    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:e,password:p})});
    const d=await r.json();
    if(d.ok){localStorage.setItem('zt',d.token);localStorage.setItem('za',d.is_admin?'1':'0');window.location.replace('/dashboard');}
    else{msg('lm',d.error||'Email ou mot de passe incorrect',false);btn.textContent='SE CONNECTER →';btn.disabled=false;}
  }catch(err){msg('lm','Erreur réseau',false);btn.textContent='SE CONNECTER →';btn.disabled=false;}
}
async function register(){
  const n=document.getElementById('rn').value.trim(),e=document.getElementById('re').value.trim(),p=document.getElementById('rp').value;
  if(!n||!e||!p){msg('rm','Remplis tous les champs',false);return;}
  if(p.length<6){msg('rm','Mot de passe trop court (min 6)',false);return;}
  const btn=document.querySelector('#f1 .btn');btn.textContent='Création...';btn.disabled=true;
  try{
    const r=await fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:n,email:e,password:p})});
    const d=await r.json();
    if(d.ok){localStorage.setItem('zt',d.token);localStorage.setItem('za',d.is_admin?'1':'0');window.location.replace('/dashboard');}
    else{msg('rm',d.error||'Erreur',false);btn.textContent='CRÉER MON COMPTE →';btn.disabled=false;}
  }catch(err){msg('rm','Erreur réseau',false);btn.textContent='CRÉER MON COMPTE →';btn.disabled=false;}
}
// Auto-redirect si déjà connecté (vérif rapide)
const t=localStorage.getItem('zt');
if(t){
  fetch('/api/me',{headers:{'Authorization':'Bearer '+t}})
    .then(r=>r.json())
    .then(d=>{if(d.ok)window.location.replace('/dashboard');})
    .catch(()=>{});
}
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
.bnt{flex:1;padding:10px 0;border:none;background:none;color:rgba(255,255,255,.28);font-size:20px;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:2px}
.bnt span{font-size:7px;font-family:'Orbitron',monospace;letter-spacing:1px}
.bnt.a{color:var(--g)}
.pg{display:none;padding:12px}.pg.a{display:block}
.logo{font-family:'Orbitron',monospace;font-size:20px;font-weight:900;color:var(--g);text-align:center;padding:10px 0 2px;letter-spacing:3px}
.sub{font-family:'Orbitron',monospace;font-size:7px;letter-spacing:5px;color:rgba(245,197,24,.2);text-align:center;margin-bottom:8px}
.sr{display:flex;align-items:center;justify-content:center;gap:7px;margin-bottom:8px}
.dot{width:8px;height:8px;border-radius:50%;background:#333}.dot.on{background:#22c55e;box-shadow:0 0 6px #22c55e}.dot.off{background:#ef4444}
.st{font-size:11px;color:rgba(255,255,255,.3)}
hr{border:none;height:1px;background:linear-gradient(90deg,transparent,rgba(245,197,24,.2),transparent);margin:8px 0}
/* PRIX TICKER */
.ticker{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px;margin-bottom:8px;-webkit-overflow-scrolling:touch;scrollbar-width:none}
.ticker::-webkit-scrollbar{display:none}
.tk{background:rgba(245,197,24,.04);border:1px solid rgba(245,197,24,.1);border-radius:10px;padding:8px 10px;min-width:80px;flex-shrink:0;position:relative;overflow:hidden}
.tk::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--tc,rgba(245,197,24,.3)),transparent)}
.tk-sym{font-family:'Orbitron',monospace;font-size:7px;color:rgba(255,255,255,.35);letter-spacing:1px}
.tk-ico{font-size:14px;margin:1px 0}
.tk-px{font-family:'Orbitron',monospace;font-size:11px;font-weight:900;color:var(--g)}
/* BALANCE */
.bal{background:rgba(245,197,24,.06);border:1px solid rgba(245,197,24,.15);border-radius:12px;padding:10px 14px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center}
.blab{font-family:'Orbitron',monospace;font-size:8px;color:rgba(255,255,255,.28);letter-spacing:1px}
.bval{font-family:'Orbitron',monospace;font-size:20px;font-weight:900;color:var(--g)}
/* STATS */
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:8px}
.sc{background:rgba(245,197,24,.03);border:1px solid rgba(245,197,24,.07);border-radius:10px;padding:7px 4px;text-align:center}
.sn{font-family:'Orbitron',monospace;font-size:14px;font-weight:900;color:var(--g)}.sl{font-size:8px;color:rgba(255,255,255,.2);margin-top:2px}
.gg{color:#22c55e}.rr{color:#ef4444}
.tt{font-family:'Orbitron',monospace;font-size:8px;letter-spacing:3px;color:rgba(245,197,24,.28);margin-bottom:6px}
/* SYMBOL SELECTOR */
.sym-row{display:flex;gap:5px;overflow-x:auto;margin-bottom:8px;-webkit-overflow-scrolling:touch;scrollbar-width:none}
.sym-row::-webkit-scrollbar{display:none}
.sym-btn{background:rgba(245,197,24,.05);border:1px solid rgba(245,197,24,.1);color:rgba(255,255,255,.45);padding:5px 10px;border-radius:8px;font-family:'Orbitron',monospace;font-size:8px;cursor:pointer;white-space:nowrap;flex-shrink:0}
.sym-btn.a{background:rgba(245,197,24,.15);border-color:rgba(245,197,24,.4);color:var(--g)}
/* BOUTONS */
.g2b{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:6px}
.btn{border:none;border-radius:10px;padding:11px 6px;font-family:'Orbitron',monospace;font-size:8px;font-weight:700;cursor:pointer;letter-spacing:1px;transition:.1s;width:100%}
.btn:active{transform:scale(.93)}
.bst{background:linear-gradient(135deg,#14532d,#166534);color:#4ade80;border:1px solid rgba(74,222,128,.2)}
.bsp{background:linear-gradient(135deg,#7f1d1d,#991b1b);color:#f87171;border:1px solid rgba(248,113,113,.2)}
.bln{background:rgba(34,197,94,.1);color:#22c55e;border:1px solid rgba(34,197,94,.15);padding:10px 4px}
.bsh{background:rgba(239,68,68,.1);color:#ef4444;border:1px solid rgba(239,68,68,.15);padding:10px 4px}
.bcl{background:rgba(245,197,24,.07);color:var(--g);border:1px solid rgba(245,197,24,.12);padding:10px 4px}
.bca{background:rgba(168,85,247,.08);color:#c084fc;border:1px solid rgba(168,85,247,.18);font-size:8px;padding:10px}
.admin-only{display:none}
/* POSITIONS */
.po{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.04);border-radius:10px;padding:9px 11px;margin-bottom:6px;position:relative;overflow:hidden}
.po.lg::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:#22c55e;box-shadow:0 0 5px #22c55e}
.po.sh::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:#ef4444;box-shadow:0 0 5px #ef4444}
.pt{display:flex;justify-content:space-between;align-items:center;margin-bottom:3px}
.py{font-family:'Orbitron',monospace;font-size:11px;font-weight:700}
.pd{font-size:8px;font-weight:700;letter-spacing:2px;padding:2px 6px;border-radius:20px}
.pd.lg{background:rgba(34,197,94,.1);color:#22c55e;border:1px solid rgba(34,197,94,.18)}
.pd.sh{background:rgba(239,68,68,.1);color:#ef4444;border:1px solid rgba(239,68,68,.18)}
.pr{display:flex;justify-content:space-between;font-size:10px;color:rgba(255,255,255,.28);margin-top:2px}
.pp{font-family:'Orbitron',monospace;font-size:12px;font-weight:900}
.tsl{display:flex;gap:5px;margin-top:3px}
.tpb{font-size:7px;padding:1px 5px;border-radius:20px;font-family:'Orbitron',monospace;background:rgba(34,197,94,.06);color:rgba(34,197,94,.5);border:1px solid rgba(34,197,94,.1)}
.slb{font-size:7px;padding:1px 5px;border-radius:20px;font-family:'Orbitron',monospace;background:rgba(239,68,68,.06);color:rgba(239,68,68,.5);border:1px solid rgba(239,68,68,.1)}
.np{text-align:center;padding:14px;color:rgba(255,255,255,.1);font-size:11px}
.toast{position:fixed;top:12px;left:50%;transform:translateX(-50%);padding:8px 16px;border-radius:20px;font-family:'Orbitron',monospace;font-size:9px;z-index:200;opacity:0;transition:.25s;pointer-events:none;white-space:nowrap}
.toast.ok{background:rgba(34,197,94,.15);border:1px solid rgba(34,197,94,.3);color:#4ade80}
.toast.er{background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.3);color:#f87171}
.toast.sv{opacity:1}
/* CHART */
.ctb{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap;align-items:center}
.sbt,.fbt{background:rgba(245,197,24,.05);border:1px solid rgba(245,197,24,.1);color:rgba(255,255,255,.42);padding:5px 10px;border-radius:8px;font-family:'Orbitron',monospace;font-size:8px;cursor:pointer}
.sbt.a,.fbt.a{background:rgba(245,197,24,.12);border-color:rgba(245,197,24,.3);color:var(--g)}
#chc{border-radius:12px;overflow:hidden;border:1px solid rgba(245,197,24,.08);height:350px}
.cif{display:flex;gap:12px;margin-top:6px;flex-wrap:wrap}
.cil{font-family:'Orbitron',monospace;font-size:9px;color:rgba(255,255,255,.28)}.cil b{color:var(--g)}
/* HISTORY */
.hss{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:10px}
.hsc{background:rgba(245,197,24,.04);border:1px solid rgba(245,197,24,.08);border-radius:10px;padding:9px 6px;text-align:center}
.hsn{font-family:'Orbitron',monospace;font-size:15px;font-weight:900;color:var(--g)}.hsl{font-size:8px;color:rgba(255,255,255,.22);margin-top:2px}
.hi{display:flex;justify-content:space-between;align-items:center;padding:8px 11px;border-bottom:1px solid rgba(255,255,255,.04)}
.his{font-size:11px;font-weight:600}.hid{font-size:8px;color:rgba(255,255,255,.18)}.hip{font-family:'Orbitron',monospace;font-size:11px;font-weight:700}
/* SETTINGS */
.sf{margin-bottom:12px}
.sf label{font-size:9px;color:rgba(255,255,255,.32);letter-spacing:2px;font-family:'Orbitron',monospace;display:block;margin-bottom:5px}
.sf input{width:100%;background:rgba(245,197,24,.04);border:1px solid rgba(245,197,24,.1);border-radius:8px;padding:10px 12px;color:#fff;font-family:'Rajdhani',sans-serif;font-size:14px;outline:none;transition:.2s}
.sf input:focus{border-color:rgba(245,197,24,.3)}
.ubadge{background:rgba(245,197,24,.05);border:1px solid rgba(245,197,24,.1);border-radius:10px;padding:10px 14px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center}
.adbg{background:rgba(245,197,24,.15);border:1px solid rgba(245,197,24,.4);color:var(--g);font-family:'Orbitron',monospace;font-size:9px;padding:3px 10px;border-radius:20px;display:none}
.logout-btn{background:rgba(239,68,68,.07);border:1px solid rgba(239,68,68,.18);color:#f87171;border-radius:8px;padding:10px;width:100%;font-family:'Orbitron',monospace;font-size:9px;cursor:pointer;letter-spacing:1px;margin-top:10px}
.rfb{height:2px;background:rgba(245,197,24,.05);margin:8px 0 4px;border-radius:1px;overflow:hidden}
.rfi{height:100%;background:var(--g);width:100%;transition:width 3s linear}
.ft{text-align:center;font-size:7px;color:rgba(255,255,255,.07);font-family:'Orbitron',monospace;letter-spacing:2px;padding-bottom:6px}
</style></head><body>
<div id="toast" class="toast"></div>

<!-- PAGE 1: TRADE -->
<div id="p1" class="pg a">
<div class="logo">⚡ ZYCRYPTO</div>
<div class="sub">MULTI-CRYPTO · CLOUD · LIVE</div>
<div class="sr"><div class="dot" id="d1"></div><span class="st" id="s1">Connexion...</span></div>

<!-- TICKER PRIX -->
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

<!-- ADMIN BOT CONTROL -->
<div class="admin-only" id="admin-ctrl">
  <div class="tt">👑 CONTRÔLE BOT — ADMIN</div>
  <div class="g2b" style="margin-bottom:10px">
    <button class="btn bst" onclick="cmd('start')">▶ DÉMARRER BOT<br><span style="font-size:7px;opacity:.5">Tous les users</span></button>
    <button class="btn bsp" onclick="cmd('stop')">⏹ ARRÊTER BOT</button>
  </div><hr>
</div>

<!-- SYMBOL SELECTOR -->
<div class="tt">📊 CHOISIR LA CRYPTO</div>
<div class="sym-row" id="sym-sel"></div>

<!-- ORDRE MANUEL -->
<div class="tt" id="trade-tt">ORDRES — BTC</div>
<div class="g2b">
  <button class="btn bln" onclick="cmd('buy')">🟢 LONG</button>
  <button class="btn bsh" onclick="cmd('sell')">🔴 SHORT</button>
</div>
<div class="g2b">
  <button class="btn bcl" onclick="cmd('close')">🔒 FERMER</button>
  <button class="btn bca" onclick="cmd('closeall')">🔒 FERMER TOUT</button>
</div>

<hr><div class="tt">⚡ POSITIONS OUVERTES</div>
<div id="pos"><div class="np">📭 Aucune position</div></div>
<div class="rfb"><div class="rfi" id="rfi"></div></div>
<div class="ft">ZYCRYPTO v1.2 · ZYPROZ · 2026</div>
</div>

<!-- PAGE 2: GRAPHIQUE -->
<div id="p2" class="pg">
<div class="logo" style="font-size:15px;padding:10px 0 4px">📈 GRAPHIQUE LIVE</div>
<div class="ctb">
  <select id="ch-sym" onchange="lc()" style="background:rgba(245,197,24,.06);border:1px solid rgba(245,197,24,.12);color:var(--g);padding:5px 10px;border-radius:8px;font-family:'Orbitron',monospace;font-size:8px;cursor:pointer">
    <option value="BTC">₿ BTC</option><option value="ETH">Ξ ETH</option>
    <option value="BNB">◈ BNB</option><option value="SOL">◎ SOL</option>
    <option value="XRP">✕ XRP</option><option value="DOGE">Ð DOGE</option>
    <option value="GOLD">🥇 OR</option>
  </select>
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
</div>

<!-- PAGE 3: HISTORIQUE -->
<div id="p3" class="pg">
<div class="logo" style="font-size:15px;padding:10px 0 4px">📋 HISTORIQUE CLOUD</div>
<div class="hss">
  <div class="hsc"><div class="hsn" id="h-t">0</div><div class="hsl">TRADES</div></div>
  <div class="hsc"><div class="hsn gg" id="h-w">0</div><div class="hsl">GAGNANTS</div></div>
  <div class="hsc"><div class="hsn" id="h-p">+0€</div><div class="hsl">PROFIT NET</div></div>
</div>
<hr><div class="tt">📜 TOUS LES TRADES</div>
<div id="hl"><div class="np">Aucun trade — données sauvegardées cloud</div></div>
</div>

<!-- PAGE 4: COMPTE -->
<div id="p4" class="pg">
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
  <div class="sf"><label>TAKE PROFIT %</label><input type="number" id="cfg-tp" value="1.0" step="0.1" min="0.1"></div>
  <div class="sf"><label>STOP LOSS %</label><input type="number" id="cfg-sl" value="0.3" step="0.1" min="0.1"></div>
</div>
<button class="btn bst" onclick="saveSettings()" style="margin-bottom:12px">💾 SAUVEGARDER</button>
<hr><div class="tt">🔗 VANTAGE LIVE (OPTIONNEL)</div>
<div class="sf"><label>META API TOKEN</label><input type="text" id="cfg-meta" placeholder="Pour trader en vrai argent"></div>
<div class="sf"><label>ACCOUNT ID</label><input type="text" id="cfg-acid" placeholder="ID compte Vantage MT5"></div>
<button class="btn" onclick="saveApi()" style="background:rgba(245,197,24,.07);color:var(--g);border:1px solid rgba(245,197,24,.18);margin-bottom:8px">🔗 CONNECTER VANTAGE</button>
<hr>
<button class="logout-btn" onclick="logout()">🚪 SE DÉCONNECTER</button>
<div class="ft" style="margin-top:10px">ZYCRYPTO v1.2 · ZYPROZ · 2026</div>
</div>

<nav class="bnav">
  <button class="bnt a" id="bn1" onclick="sp(1)">📊<span>TRADE</span></button>
  <button class="bnt" id="bn2" onclick="sp(2)">📈<span>GRAPH</span></button>
  <button class="bnt" id="bn3" onclick="sp(3)">📋<span>HISTORIQUE</span></button>
  <button class="bnt" id="bn4" onclick="sp(4)">⚙️<span>COMPTE</span></button>
</nav>

<script>
const TK=localStorage.getItem('zt'),IS_ADMIN=localStorage.getItem('za')==='1';
if(!TK){window.location.replace('/');throw 0;}

let cp=1, SEL='BTC';
const SYMS={BTC:{name:'Bitcoin',icon:'₿',color:'#f5c518'},ETH:{name:'Ethereum',icon:'Ξ',color:'#627eea'},BNB:{name:'BNB',icon:'◈',color:'#f3ba2f'},SOL:{name:'Solana',icon:'◎',color:'#9945ff'},XRP:{name:'Ripple',icon:'✕',color:'#00aae4'},DOGE:{name:'Dogecoin',icon:'Ð',color:'#c2a633'},GOLD:{name:'Or',icon:'🥇',color:'#ffd700'}};

// Afficher éléments admin
if(IS_ADMIN){document.querySelectorAll('.admin-only').forEach(e=>e.style.display='block');}

// Construire le sélecteur de symboles
const symRow=document.getElementById('sym-sel');
Object.entries(SYMS).forEach(([k,v])=>{
  const b=document.createElement('button');
  b.className='sym-btn'+(k==='BTC'?' a':'');
  b.textContent=v.icon+' '+k;
  b.onclick=()=>{SEL=k;document.querySelectorAll('.sym-btn').forEach(x=>x.classList.remove('a'));b.classList.add('a');document.getElementById('trade-tt').textContent='ORDRES — '+k;};
  symRow.appendChild(b);
});

function sp(n){document.querySelectorAll('.pg').forEach(p=>p.classList.remove('a'));document.querySelectorAll('.bnt').forEach(b=>b.classList.remove('a'));document.getElementById('p'+n).classList.add('a');document.getElementById('bn'+n).classList.add('a');cp=n;if(n===2)lc();if(n===3)rf3();if(n===4)ls();}
const H={'Content-Type':'application/json','Authorization':'Bearer '+TK};
const ff=n=>{if(n===null||n===undefined||isNaN(n))return'--';if(n>=1000)return n.toLocaleString('fr-FR',{maximumFractionDigits:2});if(n>=1)return n.toFixed(2);return n.toFixed(6);};
const pc=v=>v>=0?'gg':'rr';const ps=v=>v>=0?'+':'';
function toast(m,ok=true){const t=document.getElementById('toast');t.textContent=m;t.className='toast '+(ok?'ok':'er')+' sv';setTimeout(()=>t.classList.remove('sv'),2500);}
async function cmd(c){
  const sym=SEL;
  let endpoint=c;
  if(c==='buy') endpoint='buy_'+sym.toLowerCase();
  else if(c==='sell') endpoint='sell_'+sym.toLowerCase();
  else if(c==='close') endpoint='close_'+sym.toLowerCase();
  try{const r=await fetch('/api/cmd',{method:'POST',headers:H,body:JSON.stringify({cmd:endpoint})});if(r.status===401){window.location.replace('/');return;}
  const d=await r.json();toast(d.msg||(d.ok?'✅':'❌'),d.ok);setTimeout(rf,400);}catch(e){toast('❌',false);}
}
let _prices={};
async function rf(){
  try{
    const r=await fetch('/api/status',{headers:H});if(r.status===401){window.location.replace('/');return;}
    const d=await r.json();_prices=d.prices||{};
    document.getElementById('d1').className='dot '+(d.actif?'on':'off');
    document.getElementById('s1').textContent=d.actif?'🟢 BOT ACTIF — Trading en cours':'🔴 BOT ARRÊTÉ';
    document.getElementById('bval').textContent=ff(d.balance)+'€';
    document.getElementById('lv').textContent='x'+d.levier;document.getElementById('ms').textContent=d.mise;
    // Ticker
    const tk=document.getElementById('ticker');
    tk.innerHTML=Object.entries(_prices).map(([sym,price])=>{
      const s=SYMS[sym]||{};
      return`<div class="tk" style="--tc:${s.color||'#f5c518'}"><div class="tk-sym">${sym}</div><div class="tk-ico">${s.icon||sym}</div><div class="tk-px">$${ff(price)}</div></div>`;
    }).join('');
    // Stats
    const h=d.trades||[];const w=h.filter(t=>(t.pnl||0)>0).length;const tp=h.reduce((s,t)=>s+(t.pnl||0),0);
    document.getElementById('nt').textContent=h.length;
    const we=document.getElementById('wr');we.textContent=h.length?Math.round(w/h.length*100)+'%':'--%';we.className='sn '+(h.length&&w/h.length>=0.5?'gg':'rr');
    const te=document.getElementById('tps');te.textContent=ps(tp)+tp.toFixed(2)+'€';te.className='sn '+pc(tp);
    // Positions
    const pos=d.positions||{};const ks=Object.keys(pos);const pE=document.getElementById('pos');
    if(!ks.length){pE.innerHTML='<div class="np">📭 Aucune position — en attente de signal</div>';}
    else{pE.innerHTML=ks.map(sym=>{
      const p=pos[sym];const cpx=_prices[sym]||0;const e=parseFloat(p.e);
      const pnl=p.d==='BUY'?parseFloat(p.v)*(cpx-e):parseFloat(p.v)*(e-cpx);
      const pct=e?((p.d==='BUY'?(cpx-e)/e:(e-cpx)/e)*100):0;
      const dir=p.d==='BUY'?'lg':'sh';const s2=SYMS[sym]||{};
      return`<div class="po ${dir}"><div class="pt"><div class="py">${s2.icon||sym} ${sym}</div><div class="pd ${dir}">${p.d==='BUY'?'⬆ LONG':'⬇ SHORT'}</div></div>
      <div class="pr"><span>Entrée <b style="color:#fff">$${ff(e)}</b></span><span>Actuel <b style="color:var(--g)">$${cpx?ff(cpx):'--'}</b></span></div>
      <div class="pr" style="margin-top:3px"><span>Vol:${p.v}</span><span class="pp ${pc(pnl)}">${ps(pnl)}${Math.abs(pnl).toFixed(4)}€ (${ps(pct)}${Math.abs(pct).toFixed(2)}%)</span></div>
      <div class="tsl"><span class="tpb">TP $${ff(parseFloat(p.tp))}</span><span class="slb">SL $${ff(parseFloat(p.sl))}</span></div></div>`;
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
  if(!h.length){le.innerHTML='<div class="np">Aucun trade · Sauvegardé dans le cloud</div>';return;}
  le.innerHTML=h.map(t=>{
    const s2=SYMS[t.s]||{};const dt=t.ts?new Date(t.ts).toLocaleString('fr-FR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'';
    return`<div class="hi"><div><div class="his">${s2.icon||t.s} ${t.s} ${t.d==='BUY'?'🟢 LONG':'🔴 SHORT'}</div>
    <div class="hid">${t.r||''} · ${dt}</div>
    <div class="hid">$${ff(t.e||0)} → $${ff(t.x||0)}</div></div>
    <div class="hip ${pc(t.pnl||0)}">${ps(t.pnl||0)}${Math.abs(t.pnl||0).toFixed(4)}€</div></div>`;
  }).join('');
}
async function rf3(){try{const d=await fetch('/api/status',{headers:H}).then(r=>r.json());uh(d.trades||[]);}catch(e){}}
async function ls(){
  try{const d=await fetch('/api/me',{headers:H}).then(r=>r.json());if(!d.ok)return;
  const u=d.user;
  document.getElementById('u-name').textContent=u.username;document.getElementById('u-email').textContent=u.email;
  document.getElementById('cfg-l').value=u.levier;document.getElementById('cfg-m').value=u.mise;
  document.getElementById('cfg-tp').value=u.tp;document.getElementById('cfg-sl').value=u.sl;
  document.getElementById('cfg-meta').value=u.meta_token||'';document.getElementById('cfg-acid').value=u.account_id||'';
  if(u.is_admin){const ab=document.getElementById('adbg');if(ab)ab.style.display='inline-block';}}catch(e){}
}
async function saveSettings(){
  const b={levier:parseInt(document.getElementById('cfg-l').value),mise:parseFloat(document.getElementById('cfg-m').value),tp:parseFloat(document.getElementById('cfg-tp').value),sl:parseFloat(document.getElementById('cfg-sl').value)};
  const d=await fetch('/api/settings',{method:'POST',headers:H,body:JSON.stringify(b)}).then(r=>r.json());
  toast(d.msg||(d.ok?'✅ Sauvegardé':'❌'),d.ok);
}
async function saveApi(){
  const b={meta_token:document.getElementById('cfg-meta').value,account_id:document.getElementById('cfg-acid').value};
  const d=await fetch('/api/apikeys',{method:'POST',headers:H,body:JSON.stringify(b)}).then(r=>r.json());
  toast(d.msg||(d.ok?'✅':'❌'),d.ok);
}
function logout(){localStorage.clear();window.location.replace('/');}
let chart=null,cs=null,cT='5m';
function setTf(tf){cT=tf;['1m','5m','15m','1h'].forEach(x=>document.getElementById('fb-'+x).classList.toggle('a',x===tf));lc();}
function lc(){
  const cSym=document.getElementById('ch-sym')?.value||'BTC';
  const con=document.getElementById('chc');
  if(!chart){
    chart=LightweightCharts.createChart(con,{width:con.clientWidth,height:350,layout:{background:{color:'#07070a'},textColor:'rgba(255,255,255,0.3)'},grid:{vertLines:{color:'rgba(245,197,24,0.03)'},horzLines:{color:'rgba(245,197,24,0.03)'}},crosshair:{mode:LightweightCharts.CrosshairMode.Normal},rightPriceScale:{borderColor:'rgba(245,197,24,0.08)'},timeScale:{borderColor:'rgba(245,197,24,0.08)',timeVisible:true}});
    cs=chart.addCandlestickSeries({upColor:'#22c55e',downColor:'#ef4444',borderUpColor:'#22c55e',borderDownColor:'#ef4444',wickUpColor:'#22c55e',wickDownColor:'#ef4444'});
    chart.subscribeCrosshairMove(p=>{if(p.seriesData&&p.seriesData.size>0){const cd=p.seriesData.values().next().value;if(cd){document.getElementById('co').textContent='$'+cd.open.toFixed(4);document.getElementById('ch').textContent='$'+cd.high.toFixed(4);document.getElementById('cl').textContent='$'+cd.low.toFixed(4);document.getElementById('cc').textContent='$'+cd.close.toFixed(4);}}});
  }
  fetch(`/api/ohlc?s=${cSym}&tf=${cT}`,{headers:H}).then(r=>r.json()).then(data=>{
    if(data&&data.length){cs.setData(data.map(c=>({time:c.t,open:c.o,high:c.h,low:c.l,close:c.c})));chart.timeScale().fitContent();const l=data[data.length-1];document.getElementById('co').textContent='$'+l.o.toFixed(4);document.getElementById('ch').textContent='$'+l.h.toFixed(4);document.getElementById('cl').textContent='$'+l.l.toFixed(4);document.getElementById('cc').textContent='$'+l.c.toFixed(4);}
  }).catch(()=>{});
}
rf();setInterval(()=>{if(cp===1||cp===3)rf();},3000);setInterval(()=>{if(cp===2)lc();},10000);
</script></body></html>"""

# ══════════════════════════════════════════════════════════════
#   HTTP SERVER
# ══════════════════════════════════════════════════════════════
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def sj(self,d,c=200):
        b=json.dumps(d).encode();self.send_response(c);self.send_header("Content-Type","application/json");self.send_header("Access-Control-Allow-Origin","*");self.end_headers();self.wfile.write(b)
    def sh(self,html):
        b=html.encode();self.send_response(200);self.send_header("Content-Type","text/html;charset=utf-8");self.end_headers();self.wfile.write(b)
    def tok(self): a=self.headers.get("Authorization","");return a[7:] if a.startswith("Bearer ") else None
    def do_HEAD(self): self.send_response(200);self.send_header("Content-Type","text/plain");self.end_headers()
    def do_OPTIONS(self):
        self.send_response(200);self.send_header("Access-Control-Allow-Origin","*");self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS");self.send_header("Access-Control-Allow-Headers","Content-Type,Authorization");self.end_headers()
    def do_GET(self):
        p=self.path.split("?")[0]
        if p in("/","/login"): self.sh(LOGIN_HTML)
        elif p=="/dashboard": self.sh(DASH_HTML)
        elif p in("/ping","/health"):
            self.send_response(200);self.send_header("Content-Type","text/plain");self.end_headers();self.wfile.write(b"OK")
        elif p=="/api/me":
            u=au(self.tok())
            if not u: self.sj({"ok":False},401);return
            self.sj({"ok":True,"user":{"username":u["username"],"email":u["email"],"levier":u["levier"],"mise":u["mise"],"tp":u["tp"],"sl":u["sl"],"meta_token":u.get("meta_token",""),"account_id":u.get("account_id",""),"balance":u["balance"],"is_admin":bool(u.get("is_admin",False))}})
        elif p=="/api/status":
            u=au(self.tok())
            if not u: self.sj({"ok":False},401);return
            admin=DB.get_admin();bot_on=bool(admin and admin.get("bot_actif"))
            pos=DB.get_positions(u["id"]);trades=DB.get_trades(u["id"])
            prices=get_all_prices()
            self.sj({"ok":True,"actif":bot_on,"balance":round(float(u["balance"]),2),"levier":u["levier"],"mise":u["mise"],"prices":prices,"positions":pos,"trades":trades})
        elif p=="/api/ohlc":
            u=au(self.tok())
            if not u: self.sj([],401);return
            qs=parse_qs(urlparse(self.path).query)
            self.sj(get_ohlc(qs.get("s",["BTC"])[0],qs.get("tf",["5m"])[0]))
        else: self.send_response(404);self.end_headers()

    def do_POST(self):
        n=int(self.headers.get("Content-Length",0))
        body=json.loads(self.rfile.read(n)) if n else {}
        p=self.path

        if p=="/api/register":
            email=body.get("email","").lower().strip();username=body.get("username","").strip();pw=body.get("password","")
            if not email or not username or len(pw)<6: self.sj({"ok":False,"error":"Données invalides"});return
            is_admin=bool(ADMIN_EMAIL and email==ADMIN_EMAIL)
            u=DB.create_user(email,username,hp(pw),gt(),is_admin)
            if u: self.sj({"ok":True,"token":u["token"],"is_admin":bool(u.get("is_admin",False))})
            else: self.sj({"ok":False,"error":"Email déjà utilisé"})

        elif p=="/api/login":
            email=body.get("email","").lower().strip();pw=body.get("password","")
            u=DB.get_by_email(email)
            if u and u["password_hash"]==hp(pw):
                tok=gt();DB.update_token(email,tok)
                self.sj({"ok":True,"token":tok,"is_admin":bool(u.get("is_admin",False))})
            else: self.sj({"ok":False,"error":"Email ou mot de passe incorrect"})

        elif p=="/api/settings":
            u=au(self.tok())
            if not u: self.sj({"ok":False},401);return
            DB.update_user(u["id"],{"levier":int(body.get("levier",200)),"mise":float(body.get("mise",10)),"tp":float(body.get("tp",1.0)),"sl":float(body.get("sl",0.3))})
            self.sj({"ok":True,"msg":"✅ Paramètres sauvegardés dans le cloud"})

        elif p=="/api/apikeys":
            u=au(self.tok())
            if not u: self.sj({"ok":False},401);return
            DB.update_user(u["id"],{"meta_token":body.get("meta_token",""),"account_id":body.get("account_id","")})
            self.sj({"ok":True,"msg":"✅ Clés API sauvegardées"})

        elif p=="/api/cmd":
            u=au(self.tok())
            if not u: self.sj({"ok":False,"redirect":"/"},401);return
            c=body.get("cmd","");uid=u["id"];ok=True;msg=""

            if c in("start","stop"):
                if not u.get("is_admin"): self.sj({"ok":False,"msg":"❌ Admin uniquement"});return
                actif=(c=="start")
                DB.update_user(uid,{"bot_actif":actif})
                if actif: ensure_thread(uid);msg="🟢 Bot démarré !";tg(f"🚀 *ZyCrypto Bot démarré* par {u['username']}")
                else: msg="⏹ Bot arrêté"

            elif c=="closeall":
                # Fermer tout sans besoin de symbole
                pos=DB.get_positions(uid);tot=0
                if pos:
                    for sk in list(pos.keys()):
                        cp=get_price(sk) or float(pos[sk]["e"])
                        pnl=close_trade(uid,sk,cp,"🔒 Fermer tout")
                        if pnl is not None: tot+=pnl
                    u2=DB.get_by_id(uid)
                    msg=f"🔒 Tout fermé | {tot:+.4f}€ | Solde: {u2['balance']:.2f}€"
                    tg(f"🔒 *Tout fermé* ({u['username']}) | `{tot:+.4f}€`")
                else: ok=False;msg="Rien à fermer"

            else:
                # Détecter le symbole depuis la commande
                sym=None
                for s in SYMBOLS:
                    if s.lower() in c: sym=s; break
                if not sym: self.sj({"ok":False,"msg":"❌ Commande inconnue"}); return

                if "buy" in c or "long" in c:
                    price=get_price(sym)
                    if price and price>0:
                        t=open_trade(uid,sym,"BUY",price)
                        if t:
                            msg=f"🟢 LONG {SYMBOLS[sym]['icon']} {sym} @ ${price:.4f}"
                            tg(f"⚡ *{msg}* ({u['username']})")
                        else: ok=False;msg="❌ Solde insuffisant"
                    else: ok=False;msg="❌ Prix indisponible"

                elif "sell" in c or "short" in c:
                    price=get_price(sym)
                    if price and price>0:
                        t=open_trade(uid,sym,"SELL",price)
                        if t:
                            msg=f"🔴 SHORT {SYMBOLS[sym]['icon']} {sym} @ ${price:.4f}"
                            tg(f"⚡ *{msg}* ({u['username']})")
                        else: ok=False;msg="❌ Solde insuffisant"
                    else: ok=False;msg="❌ Prix indisponible"

                elif "close" in c:
                    price=get_price(sym)
                    if price and price>0:
                        pnl=close_trade(uid,sym,price,"🔒 Fermeture manuelle")
                        if pnl is not None:
                            u2=DB.get_by_id(uid)
                            msg=f"🔒 {sym} fermé | {pnl:+.4f}€ | Solde: {u2['balance']:.2f}€"
                            tg(f"🔒 *{sym}* ({u['username']}) | `{pnl:+.4f}€`")
                        else: ok=False;msg=f"Pas de position {sym}"
                    else: ok=False;msg="❌ Prix indisponible"

            self.sj({"ok":ok,"msg":msg})
        else: self.send_response(404);self.end_headers()

def run():
    import socket as sk
    class S(HTTPServer):
        allow_reuse_address=True
        def server_bind(self): self.socket.setsockopt(sk.SOL_SOCKET,sk.SO_REUSEADDR,1);super().server_bind()
    print(f"⚡ ZYCRYPTO PLATFORM v1.2")
    print(f"   DB: GitHub Gist ({'✅' if GH_TOKEN and GIST_ID else '⚠️  manque GH_TOKEN/GIST_ID'})")
    print(f"   Admin: {ADMIN_EMAIL}")
    print(f"   Symboles: {', '.join(SYMBOLS.keys())}")
    print(f"   Port: {PORT}")
    DB.load()
    threading.Thread(target=start_all,daemon=True).start()
    S(("0.0.0.0",PORT),H).serve_forever()

if __name__=="__main__":
    run()
