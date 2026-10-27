"""MH Gold Radar - five pages: Dashboard, What Moves Gold, News & AI Summary, Gold History, Learn Gold.

Shows gold next to the dollar index, the 10-year Treasury yield and inflation,
plus a placeholder daily summary and a price-alert box, over a moving black
and gold background (gold network, small gold bars and rising $ signs).
Live prices come from Yahoo Finance (via yfinance, delayed about 10-15 min),
inflation from FRED, and headlines from Google News. If the internet is down,
the page falls back to sample data. The daily summary is written by Claude
(Anthropic API key read from the ANTHROPIC_API_KEY setting).
"""

import html
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="MH Gold Radar", page_icon="🪙", layout="wide")

GOLD = "#F5D76E"
GOLD_DEEP = "#D4AF37"
IVORY = "#F3EAD2"
MUTED = "#A89C7A"
BLACK = "#0A0908"

# ---------- Black and gold styling ----------
STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700;800&family=Public+Sans:wght@400;500;600;700&display=swap');

html, body { background: #000000 !important; color-scheme: dark; }
.stApp, [data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background: transparent !important; }
.stApp { color: #FFFFFF; font-family: 'Public Sans', system-ui, sans-serif; font-size: 14px; }
[data-testid="stMainBlockContainer"] {
    background: rgba(0, 0, 0, .55); border-radius: 18px; margin-top: 1.2rem; padding-top: 2.4rem;
    border: 1px solid rgba(212, 175, 55, .25);
}

/* All text: bold and white */
.stApp p, .stApp li, .stApp label, .stApp span, .stApp small, .stApp div { color: #FFFFFF; }
.stApp p, .stApp li, .stApp label, .stApp small { font-weight: 400 !important; font-size: 14px; }
h1 { font-size: 1.8rem !important; }
h2, h3 { font-size: 1.15rem !important; font-weight: 600 !important; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: #FFFFFF !important; opacity: .8; font-weight: 400 !important; font-size: 12.5px !important; }
h1, h2, h3 { font-family: 'Bricolage Grotesque', 'Segoe UI', sans-serif !important; color: #FFFFFF !important; font-weight: 600 !important; letter-spacing: 0; }
[data-testid="stMetricLabel"] p { color: #FFFFFF !important; font-weight: 400 !important; }
[data-testid="stMetricValue"] { color: #FFFFFF !important; font-weight: 500 !important; font-size: 1.35rem !important; font-family: 'Public Sans', sans-serif; }
[data-testid="stAlert"] { background: rgba(212, 175, 55, .12) !important; border: 1px solid rgba(212, 175, 55, .45); }
[data-testid="stAlert"] p { color: #FFFFFF !important; }
hr { border-color: rgba(212, 175, 55, .35) !important; }

input, textarea, [data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="base-input"] {
    background-color: #15120B !important; color: #FFFFFF !important; border-color: #3A3120 !important; font-weight: 400 !important;
}
[data-baseweb="select"] > div { background-color: #15120B !important; border: 1px solid rgba(212,175,55,.45) !important; border-radius: 10px !important; }
[data-baseweb="select"] input { background: transparent !important; }
[data-baseweb="input"], [data-baseweb="base-input"], [data-testid="stNumberInput"] > div > div, [data-testid="stTextInput"] > div > div {
    border: 1px solid rgba(212,175,55,.45) !important; border-radius: 10px !important; background-color: #15120B !important; }
[data-baseweb="input"] > div, [data-baseweb="base-input"] input, [data-testid="stNumberInput"] input, [data-testid="stTextInput"] input { border: 0 !important; }
[data-testid="stMultiSelect"] > div > div, [data-testid="stMultiSelect"] [data-baseweb="select"] { background-color: #15120B !important; }
[data-baseweb="select"] svg { fill: #F5D76E !important; color: #F5D76E !important; }
[data-baseweb="tag"] { background-color: #D4AF37 !important; }
[data-baseweb="tag"] span { color: #000000 !important; }
[data-baseweb="popover"] li, [data-baseweb="menu"] { background-color: #15120B !important; }
[data-testid="stNumberInput"] button { background-color: #15120B !important; color: #F5D76E !important; }

.stButton > button {
    background: #D4AF37; color: #000000; border: 0; font-weight: 500; border-radius: 10px; padding: .55rem 1.2rem;
}
.stButton > button:hover { background: #F5D76E; color: #000000; }
.stButton > button p { color: #000000 !important; }

/* Price cards, performance table, news */
.mh-card { background: rgba(10,10,10,.75); border: 1px solid rgba(212,175,55,.35); border-radius: 14px; padding: 14px 18px 6px; }
.mh-card .mh-name { color: #F5D76E; font-weight: 600; font-size: .85rem; letter-spacing: .02em; }
.mh-card .mh-price { color: #FFFFFF; font-weight: 600; font-size: 1.55rem; font-family: 'Public Sans', sans-serif; line-height: 1.1; }
.mh-up { color: #00E676 !important; font-weight: 400; }
.mh-down { color: #FF3D57 !important; font-weight: 400; }
.mh-flat { color: #FFFFFF !important; font-weight: 400; }
.mh-card .mh-chg { font-size: .9rem; }
.mh-card .mh-sub { color: #CFC6AE !important; font-size: .75rem; font-weight: 400; }
table.mh-perf { width: 100%; border-collapse: collapse; background: rgba(10,10,10,.75); border: 1px solid rgba(212,175,55,.35); border-radius: 14px; overflow: hidden; }
table.mh-perf caption { caption-side: top; color: #F5D76E; font-weight: 600; font-size: .85rem; padding: 10px 14px; text-align: left; background: rgba(10,10,10,.75); border: 1px solid rgba(212,175,55,.35); border-bottom: 0; border-radius: 14px 14px 0 0; }
table.mh-perf th { color: #FFFFFF; font-weight: 500; font-size: .82rem; text-align: right; padding: 8px 14px; border-bottom: 1px solid rgba(212,175,55,.35); }
table.mh-perf th:first-child, table.mh-perf td:first-child { text-align: left; }
table.mh-perf td { padding: 7px 14px; text-align: right; font-weight: 400; font-size: .82rem; color: #FFFFFF; border-bottom: 1px solid rgba(255,255,255,.06); }
table.mh-perf tr:nth-child(even) td { background: rgba(255,255,255,.03); }
.mh-news { background: rgba(10,10,10,.75); border: 1px solid rgba(212,175,55,.25); border-left: 4px solid #D4AF37; border-radius: 10px; padding: 12px 16px; margin-bottom: 10px; text-decoration: none !important; }
.mh-news:hover { border-color: #F5D76E; background: rgba(212,175,55,.10); }
.mh-news .mh-title, .mh-news .mh-title a { color: #FFFFFF !important; font-weight: 400; font-size: .88rem; text-decoration: none !important; }
.mh-news .mh-title a:hover { color: #F5D76E !important; text-decoration: underline !important; }
.mh-news .mh-meta { color: #F5D76E !important; font-weight: 400; font-size: .75rem; margin-top: 4px; }
.mh-tag { display: inline-block; padding: 1px 7px; border-radius: 999px; font-size: .65rem; font-weight: 600; margin-right: 6px; color: #000 !important; }
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)

# ---------- Moving background: gold network + gold bars + rising $ signs ----------
BACKGROUND_JS = """
<script>
(function () {
  var P = window.parent, doc = P.document;
  var alive = P.__mhBeat && (Date.now() - P.__mhBeat < 2000) && doc.getElementById('mh-bg');
  if (alive) return;
  var gen = (P.__mhGen = (P.__mhGen || 0) + 1);
  var old = doc.getElementById('mh-bg'); if (old) old.remove();

  var canvas = doc.createElement('canvas');
  canvas.id = 'mh-bg';
  canvas.setAttribute('aria-hidden', 'true');
  canvas.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:-1;pointer-events:none;';
  doc.body.prepend(canvas);
  var ctx = canvas.getContext('2d');

  var reduce = P.matchMedia && P.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var W = 0, H = 0, lastW = 0, dpr = 1;
  var nodes = [], edges = [], nbrs = [], sparks = [], rings = [], floaters = [];
  var mouse = { x: -9999, y: -9999, on: false };
  var spawnIn = 700;

  function reach() { return Math.min(170, Math.max(110, W / 9)); }

  function resize() {
    dpr = Math.min(P.devicePixelRatio || 1, 2);
    W = P.innerWidth; H = P.innerHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (!nodes.length || W !== lastW) {
      var count = Math.round(Math.min(90, Math.max(26, (W * H) / 17000)));
      nodes = [];
      for (var i = 0; i < count; i++) {
        nodes.push({ x: Math.random() * W, y: Math.random() * H,
          vx: (Math.random() - .5) * .26, vy: (Math.random() - .5) * .26, flash: 0 });
      }
      sparks = []; rings = [];
      floaters = [];
      var nBars = Math.round(Math.min(14, Math.max(7, W / 130)));
      var nDollars = Math.round(Math.min(26, Math.max(12, W / 70)));
      for (var b = 0; b < nBars; b++) floaters.push(makeFloater('bar', true));
      for (var c = 0; c < nDollars; c++) floaters.push(makeFloater('dollar', true));
    }
    lastW = W;
    if (reduce) { link(); draw(); }
  }

  function makeFloater(kind, anywhere) {
    var bar = kind === 'bar';
    return { kind: kind,
      x: Math.random() * W,
      y: anywhere ? Math.random() * H : H + 40,
      size: bar ? 34 + Math.random() * 22 : 18 + Math.random() * 18,
      vy: bar ? .22 + Math.random() * .22 : .30 + Math.random() * .30,
      sway: Math.random() * 6.28, swaySpeed: .006 + Math.random() * .01,
      tilt: (Math.random() - .5) * .3,
      alpha: bar ? .55 + Math.random() * .3 : .16 + Math.random() * .14 };
  }

  function drawBar(f) {
    var w = f.size, h = f.size * .48, top = w * .16;
    ctx.save();
    ctx.translate(f.x + Math.sin(f.sway) * 10, f.y);
    ctx.rotate(f.tilt + Math.sin(f.sway) * .12);
    ctx.globalAlpha = f.alpha;
    ctx.shadowColor = 'rgba(212,175,55,.6)'; ctx.shadowBlur = 14;
    var g = ctx.createLinearGradient(0, -h / 2, 0, h / 2);
    g.addColorStop(0, '#FFF1B8'); g.addColorStop(.35, '#F2CF5B');
    g.addColorStop(.7, '#C9A227'); g.addColorStop(1, '#8C6A14');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.moveTo(-w / 2 + top, -h / 2); ctx.lineTo(w / 2 - top, -h / 2);
    ctx.lineTo(w / 2, h / 2); ctx.lineTo(-w / 2, h / 2); ctx.closePath();
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.strokeStyle = 'rgba(255,241,184,.7)'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(-w / 2 + top + 2, -h / 2 + 2); ctx.lineTo(w / 2 - top - 2, -h / 2 + 2); ctx.stroke();
    ctx.restore();
  }

  function drawDollar(f) {
    ctx.save();
    ctx.globalAlpha = f.alpha;
    ctx.fillStyle = '#D4AF37';
    ctx.font = '700 ' + f.size.toFixed(0) + 'px Georgia, serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('$', f.x + Math.sin(f.sway) * 8, f.y);
    ctx.restore();
  }

  function link() {
    var d = reach(), d2 = d * d;
    edges = []; nbrs = nodes.map(function () { return []; });
    for (var i = 0; i < nodes.length; i++) {
      for (var j = i + 1; j < nodes.length; j++) {
        var dx = nodes[i].x - nodes[j].x, dy = nodes[i].y - nodes[j].y, dd = dx * dx + dy * dy;
        if (dd < d2) { edges.push([i, j, dd]); nbrs[i].push(j); nbrs[j].push(i); }
      }
    }
  }

  function arrive(s, node) {
    s.dead = true;
    nodes[node].flash = 1;
    rings.push({ x: nodes[node].x, y: nodes[node].y, r: 3, max: 46, a: .8 });
  }

  function spawn() {
    if (sparks.length >= 6) return;
    var pool = [];
    for (var i = 0; i < nodes.length; i++) if (nbrs[i].length) pool.push(i);
    if (!pool.length) return;
    var a = pool[(Math.random() * pool.length) | 0];
    var b = nbrs[a][(Math.random() * nbrs[a].length) | 0];
    sparks.push({ a: a, b: b, t: 0, speed: .010 + Math.random() * .008,
      hops: 2 + ((Math.random() * 3) | 0), x: nodes[a].x, y: nodes[a].y, ax: nodes[a].x, ay: nodes[a].y });
  }

  function step(dt) {
    for (var k = 0; k < nodes.length; k++) {
      var n = nodes[k];
      n.x += n.vx * dt; n.y += n.vy * dt;
      if (n.x < -20) n.x = W + 20; else if (n.x > W + 20) n.x = -20;
      if (n.y < -20) n.y = H + 20; else if (n.y > H + 20) n.y = -20;
      if (mouse.on) {
        var dx = n.x - mouse.x, dy = n.y - mouse.y, m2 = dx * dx + dy * dy;
        if (m2 < 16900 && m2 > 1) {
          var m = Math.sqrt(m2), f = (1 - m / 130) * .35 * dt;
          n.x += (dx / m) * f * 3; n.y += (dy / m) * f * 3;
        }
      }
      n.flash = Math.max(0, n.flash - dt * .025);
    }
    link();
    spawnIn -= dt * 16.67;
    if (spawnIn <= 0) { spawn(); spawnIn = 1100 + Math.random() * 1400; }

    for (var q = 0; q < sparks.length; q++) {
      var s = sparks[q];
      s.t += s.speed * dt;
      var A = nodes[s.a], B = nodes[s.b], t = Math.min(s.t, 1);
      s.ax = A.x; s.ay = A.y;
      s.x = A.x + (B.x - A.x) * t; s.y = A.y + (B.y - A.y) * t;
      if (s.t >= 1) {
        s.hops--;
        var opts = nbrs[s.b].filter(function (z) { return z !== s.a; });
        if (s.hops <= 0 || !opts.length) arrive(s, s.b);
        else { s.a = s.b; s.b = opts[(Math.random() * opts.length) | 0]; s.t = 0; }
      }
    }
    sparks = sparks.filter(function (z) { return !z.dead; });

    for (var r = 0; r < rings.length; r++) {
      rings[r].r += 1.6 * dt;
      rings[r].a = Math.max(0, 1 - rings[r].r / rings[r].max) * .8;
    }
    rings = rings.filter(function (z) { return z.r < z.max; });

    for (var f = 0; f < floaters.length; f++) {
      var fl = floaters[f];
      fl.y -= fl.vy * dt; fl.sway += fl.swaySpeed * dt;
      if (fl.y < -60) floaters[f] = makeFloater(fl.kind, false);
    }
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    for (var fd = 0; fd < floaters.length; fd++) if (floaters[fd].kind === 'dollar') drawDollar(floaters[fd]);
    var d = reach();
    ctx.lineWidth = 1;
    for (var e = 0; e < edges.length; e++) {
      var ed = edges[e], a = 1 - Math.sqrt(ed[2]) / d;
      ctx.strokeStyle = 'rgba(212,175,55,' + (a * .30).toFixed(3) + ')';
      ctx.beginPath(); ctx.moveTo(nodes[ed[0]].x, nodes[ed[0]].y); ctx.lineTo(nodes[ed[1]].x, nodes[ed[1]].y); ctx.stroke();
    }
    if (mouse.on) {
      for (var i = 0; i < nodes.length; i++) {
        var dx = nodes[i].x - mouse.x, dy = nodes[i].y - mouse.y, m = Math.sqrt(dx * dx + dy * dy);
        if (m < 150) {
          ctx.strokeStyle = 'rgba(245,215,110,' + ((1 - m / 150) * .5).toFixed(3) + ')';
          ctx.beginPath(); ctx.moveTo(nodes[i].x, nodes[i].y); ctx.lineTo(mouse.x, mouse.y); ctx.stroke();
        }
      }
    }
    for (var k = 0; k < nodes.length; k++) {
      var n = nodes[k];
      ctx.fillStyle = 'rgba(245,215,110,.65)';
      ctx.beginPath(); ctx.arc(n.x, n.y, 1.8, 0, 6.2832); ctx.fill();
      if (n.flash > 0) {
        ctx.fillStyle = 'rgba(255,233,160,' + (n.flash * .85).toFixed(3) + ')';
        ctx.beginPath(); ctx.arc(n.x, n.y, 3 + n.flash * 4, 0, 6.2832); ctx.fill();
      }
    }
    for (var p = 0; p < sparks.length; p++) {
      var s = sparks[p], ang = Math.atan2(s.y - s.ay, s.x - s.ax);
      ctx.strokeStyle = 'rgba(255,233,160,.55)'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(s.x - Math.cos(ang) * 22, s.y - Math.sin(ang) * 22); ctx.lineTo(s.x, s.y); ctx.stroke();
      ctx.fillStyle = 'rgba(245,215,110,.2)';
      ctx.beginPath(); ctx.arc(s.x, s.y, 9, 0, 6.2832); ctx.fill();
      ctx.fillStyle = '#FFE9A0';
      ctx.beginPath(); ctx.arc(s.x, s.y, 3.2, 0, 6.2832); ctx.fill();
    }
    ctx.lineWidth = 1.5;
    for (var r = 0; r < rings.length; r++) {
      ctx.strokeStyle = 'rgba(245,215,110,' + rings[r].a.toFixed(3) + ')';
      ctx.beginPath(); ctx.arc(rings[r].x, rings[r].y, rings[r].r, 0, 6.2832); ctx.stroke();
    }
    for (var fb = 0; fb < floaters.length; fb++) if (floaters[fb].kind === 'bar') drawBar(floaters[fb]);
  }

  var last = P.performance.now();
  function frame(now) {
    if (P.__mhGen !== gen) return;
    P.__mhBeat = Date.now();
    var dt = Math.min(2.5, (now - last) / 16.67); last = now;
    if (!doc.hidden) { step(dt); draw(); }
    P.requestAnimationFrame(frame);
  }

  P.addEventListener('resize', resize);
  P.addEventListener('pointermove', function (e) { mouse.x = e.clientX; mouse.y = e.clientY; mouse.on = e.pointerType !== 'touch'; });
  doc.addEventListener('pointerleave', function () { mouse.on = false; });

  P.__mhBeat = Date.now();
  resize();
  if (!reduce) P.requestAnimationFrame(frame);
})();
</script>
"""
st.iframe(BACKGROUND_JS, height=1)



# ---------- Live data ----------
UP, DOWN = "#00E676", "#FF3D57"
TICKERS = {"gold": "GC=F", "silver": "SI=F", "dollar": "DX-Y.NYB", "yield10": "^TNX"}


def _naive(index):
    index = pd.to_datetime(index)
    return index.tz_localize(None) if index.tz is not None else index


@st.cache_data(ttl=300, show_spinner="Getting live gold and silver prices...")
def load_live():
    """Daily history (as far back as Yahoo has it) + 5-day intraday for gold and silver."""
    import yfinance as yf
    daily, intraday = {}, {}
    for key, sym in TICKERS.items():
        h = yf.Ticker(sym).history(period="max", interval="1d", auto_adjust=False)
        if h is None or h.empty:
            raise RuntimeError(f"No data for {sym}")
        h = h[["Open", "High", "Low", "Close"]].dropna()
        h.index = _naive(h.index).normalize()
        daily[key] = h[~h.index.duplicated(keep="last")]
    for key in ("gold", "silver"):
        i = yf.Ticker(TICKERS[key]).history(period="5d", interval="30m")
        if i is not None and not i.empty:
            i.index = _naive(i.index)
            intraday[key] = i["Close"].dropna()
    return daily, intraday


@st.cache_data(ttl=6 * 3600)
def load_cpi_yoy():
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 MHGoldRadar"})
    with urllib.request.urlopen(req, timeout=10) as r:
        cpi = pd.read_csv(r)
    s = pd.Series(cpi.iloc[:, 1].values, index=pd.to_datetime(cpi.iloc[:, 0])).dropna()
    return float((s.iloc[-1] / s.iloc[-13] - 1) * 100), s.index[-1].strftime("%b %Y")


def parse_news(xml_bytes, limit=8):
    root = ET.fromstring(xml_bytes)
    items, seen = [], set()
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        source = (it.findtext("source") or "").strip()
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)]
        try:
            when = parsedate_to_datetime(it.findtext("pubDate"))
        except Exception:
            when = None
        key = " ".join(title.lower().split())
        if key in seen:
            continue
        seen.add(key)
        items.append({"title": title, "link": it.findtext("link") or "#", "source": source, "when": when})
        if len(items) >= limit:
            break
    return items


@st.cache_data(ttl=900)
def load_news():
    q = 'gold price OR "gold market" OR "Federal Reserve" OR "interest rates" when:3d'
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q)
           + "&hl=en-US&gl=US&ceid=US:en")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 MHGoldRadar"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return parse_news(r.read())


# ---------- Sample data (used only if live data can't be reached) ----------
@st.cache_data
def make_sample_data(days: int = 180):
    rng = np.random.default_rng(42)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)

    def ohlc(start, drift, vol):
        close = start + np.cumsum(rng.normal(drift, vol, days))
        open_ = np.r_[close[0], close[:-1]]
        high = np.maximum(open_, close) + np.abs(rng.normal(0, vol * .4, days))
        low = np.minimum(open_, close) - np.abs(rng.normal(0, vol * .4, days))
        return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close}, index=dates)

    daily = {"gold": ohlc(4300, 3, 28), "silver": ohlc(50, .02, .6),
             "dollar": ohlc(100, -.02, .35), "yield10": ohlc(4.2, 0, .04)}
    times = pd.date_range(end=pd.Timestamp.now().floor("30min"), periods=5 * 46, freq="30min")
    intraday = {"gold": pd.Series(daily["gold"]["Close"].iloc[-1] + np.cumsum(rng.normal(0, 4, len(times))), index=times),
                "silver": pd.Series(daily["silver"]["Close"].iloc[-1] + np.cumsum(rng.normal(0, .08, len(times))), index=times)}
    return daily, intraday


live = True
try:
    daily, intraday = load_live()
except Exception as exc:  # no internet, yfinance missing, Yahoo down...
    live = False
    live_error = str(exc)
    daily, intraday = make_sample_data()

try:
    inflation_cpi, cpi_month = load_cpi_yoy()
except Exception:
    inflation_cpi, cpi_month = 3.1, "sample"


def last_two(key):
    c = daily[key]["Close"]
    return float(c.iloc[-1]), float(c.iloc[-2])


def change_since(series, offset):
    """Price change from the last close at or before (latest date - offset)."""
    if offset is None:
        base = series.iloc[-2]
    else:
        target = series.index[-1] - offset
        if target < series.index[0]:
            return None, None
        base = series.loc[:target].iloc[-1]
    now = series.iloc[-1]
    return float(now - base), float((now / base - 1) * 100)


def cls(v):
    return "mh-up" if v and v > 0 else ("mh-down" if v and v < 0 else "mh-flat")


def arrow(v):
    return "▲" if v > 0 else ("▼" if v < 0 else "■")



# ---------- Numbers every page uses ----------
gold_now, gold_prev = last_two("gold")
silver_now, silver_prev = last_two("silver")
dollar_now, dollar_prev = last_two("dollar")
y_now, y_prev = last_two("yield10")

# ---------- AI daily summary ----------
AI_MODEL = "claude-haiku-5-5"   # small, fast, low-cost Claude model


def _clean_key():
    """Read the AI key from this computer or from Streamlit Secrets, minus hidden characters."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        try:
            key = st.secrets["ANTHROPIC_API_KEY"]  # hidden secret on Streamlit Cloud
        except Exception:
            key = None
    return "".join(ch for ch in (key or "") if 33 <= ord(ch) <= 126)


@st.cache_data(ttl=24 * 3600, show_spinner="Writing today's AI summary...")
def ai_summary(day: str, _facts: str) -> str:
    """Ask Claude for a short plain-English summary. Written once per day for all visitors."""
    import anthropic
    key = _clean_key() or None
    client = anthropic.Anthropic(api_key=key, max_retries=3)
    msg = client.messages.create(
        model=AI_MODEL,
        max_tokens=2000,
        system=(
            "You write the daily summary for MH Gold Radar, a gold market app for everyday "
            "investors. Write 3 to 4 short sentences in plain, friendly English that a beginner "
            "understands. Explain what gold and silver did and the most likely reasons, using only "
            "the numbers and headlines given. Mention the dollar or yields only if they help explain "
            "the move. Do not predict prices and do not tell anyone to buy or sell. No headings, "
            "no bullet points, no emojis."
        ),
        messages=[{"role": "user", "content": f"Today is {day}. Market data:\n{_facts}"}],
    )
    text = "".join(getattr(b, "text", "") for b in msg.content if b.type == "text").strip()
    if not text:  # raising means an empty answer is never saved for the day
        raise RuntimeError(f"empty reply from the AI (stop reason: {msg.stop_reason}, "
                           f"parts: {', '.join(b.type for b in msg.content) or 'none'})")
    return text



def page_dashboard():
    # ---------- Gold and silver price cards + performance table ----------
    def price_card(key, name, decimals):
        now, prev = last_two(key)
        chg, pct = now - prev, (now / prev - 1) * 100
        st.markdown(
            f'<div class="mh-card"><div class="mh-name">{name}</div>'
            f'<div class="mh-price">${now:,.{decimals}f}</div>'
            f'<div class="mh-chg {cls(chg)}">{arrow(chg)} {chg:+,.{decimals}f} &nbsp; {pct:+.2f}%</div>'
            f'<div class="mh-sub">per troy ounce, USD · change vs previous close</div></div>',
            unsafe_allow_html=True)
        s = intraday.get(key)
        if s is not None and len(s) > 2:
            colr = UP if chg >= 0 else DOWN
            fill = "rgba(0,230,118,.15)" if chg >= 0 else "rgba(255,61,87,.15)"
            mini = go.Figure(go.Scatter(x=s.index, y=s.values, mode="lines", line=dict(color=colr, width=2.5),
                                        fill="tozeroy", fillcolor=fill, hovertemplate="%{x|%b %d %I:%M %p}<br>$%{y:,.2f}<extra></extra>"))
            pad = (s.max() - s.min()) * .15 or 1
            mini.update_layout(height=170, margin=dict(l=45, r=10, t=8, b=25), showlegend=False,
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,.35)",
                               font=dict(color="#FFFFFF", size=11),
                               xaxis=dict(gridcolor="#2A2418", tickformat="%a",
                                          rangebreaks=[dict(bounds=["sat", "mon"])]),
                               yaxis=dict(gridcolor="#2A2418", range=[s.min() - pad, s.max() + pad]))
            st.plotly_chart(mini, width="stretch", theme=None, config={"displayModeBar": False})
            st.caption("Last 5 trading days, every 30 minutes (weekends skipped)")


    def perf_table():
        periods = [("Today", None), ("30 Days", pd.DateOffset(days=30)), ("6 Months", pd.DateOffset(months=6)),
                   ("1 Year", pd.DateOffset(years=1)), ("5 Years", pd.DateOffset(years=5)),
                   ("20 Years", pd.DateOffset(years=20))]
        g, s = daily["gold"]["Close"], daily["silver"]["Close"]
        rows = ""
        for label, off in periods:
            ga, gp = change_since(g, off)
            sa, sp = change_since(s, off)
            cell = lambda v, fmt: f'<td class="{cls(v)}">{fmt.format(v)}</td>' if v is not None else "<td>—</td>"
            rows += f"<tr><td>{label}</td>{cell(ga, '{:+,.2f}')}{cell(gp, '{:+.2f}%')}{cell(sp, '{:+.2f}%')}</tr>"
        st.markdown(
            '<table class="mh-perf"><caption>Performance (USD)</caption>'
            "<tr><th>Change</th><th>Gold $</th><th>Gold %</th><th>Silver %</th></tr>"
            f"{rows}</table>", unsafe_allow_html=True)


    p1, p2, p3 = st.columns([1, 1, 1.1])
    with p1:
        price_card("gold", "GOLD PRICE", 2)
    with p2:
        price_card("silver", "SILVER PRICE", 2)
    with p3:
        perf_table()
        gold_now, _ = last_two("gold")
        silver_now, _ = last_two("silver")
        st.markdown(f'<div class="mh-card" style="margin-top:12px"><div class="mh-name">GOLD / SILVER RATIO</div>'
                    f'<div class="mh-price">{gold_now / silver_now:,.1f}</div>'
                    f'<div class="mh-sub">ounces of silver to buy one ounce of gold</div></div>',
                    unsafe_allow_html=True)

    # ---------- Alerts (saved in a later step) ----------
    st.subheader("Price alert")
    a1, a2 = st.columns(2)
    target = a1.number_input("Alert me when gold crosses ($/oz)",
                             value=float(round(gold_now, -1)), step=10.0)
    email = a2.text_input("Email")
    if st.button("Set alert"):
        st.success(f"Demo only: alert for ${target:,.0f} would be saved for {email or 'your email'}.")


def page_moves():
    # ---------- Dollar, yields, inflation ----------
    st.subheader("What moves gold")
    dollar_now, dollar_prev = last_two("dollar")
    y_now, y_prev = last_two("yield10")
    m1, m2, m3 = st.columns(3)
    m1.metric("Dollar Index", f"{dollar_now:.2f}", f"{dollar_now - dollar_prev:+.2f}")
    m2.metric("10Y Treasury Yield", f"{y_now:.2f}%", f"{y_now - y_prev:+.2f}")
    m3.metric("Inflation (CPI, yearly)", f"{inflation_cpi:.1f}%",
              help=f"Consumer Price Index vs 12 months earlier, latest month: {cpi_month}")

    # ---------- Chart (colorful candlesticks + levels + notes), last 6 months ----------
    st.subheader("Gold vs the dollar and yields (last 6 months)")
    options = st.multiselect(
        "Compare gold with:",
        ["Dollar Index", "10Y Yield (%)"],
        default=["Dollar Index"],
    )

    gd = daily["gold"].loc[daily["gold"].index[-1] - pd.DateOffset(months=6):]
    compare = {
        "Dollar Index": daily["dollar"]["Close"].reindex(gd.index, method="ffill"),
        "10Y Yield (%)": daily["yield10"]["Close"].reindex(gd.index, method="ffill"),
    }
    open_, high, low, close = gd["Open"], gd["High"], gd["Low"], gd["Close"]
    compare_colors = {"Dollar Index": "#00B8FF", "10Y Yield (%)": "#FF4FD8"}

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=gd.index, open=open_, high=high, low=low, close=close, name="Gold ($/oz)",
        increasing=dict(line=dict(color=UP, width=1), fillcolor=UP),
        decreasing=dict(line=dict(color=DOWN, width=1), fillcolor=DOWN),
    ))
    fig.add_trace(go.Scatter(x=gd.index, y=close.rolling(20).mean(), name="20-day average",
                             line=dict(color="#FFD60A", width=2.5)))
    for col in options:
        fig.add_trace(go.Scatter(x=gd.index, y=compare[col], name=col, yaxis="y2",
                                 line=dict(width=2.5, dash="dot", color=compare_colors[col])))

    hi_i, lo_i = high.idxmax(), low.idxmin()
    hi_v, lo_v = float(high.max()), float(low.min())
    fib_colors = {0.236: "#FF9F1C", 0.382: "#FF4FD8", 0.5: "#00B8FF", 0.618: "#00E676"}
    for lvl, colr in fib_colors.items():
        y = hi_v - (hi_v - lo_v) * lvl
        fig.add_hline(y=y, line=dict(color=colr, width=1.3, dash="dash"),
                      annotation_text=f"Fib {lvl:.3f}  ${y:,.0f}", annotation_position="top left",
                      annotation_font=dict(color=colr, size=12))

    fig.add_annotation(x=hi_i, y=hi_v, text=f"High ${hi_v:,.0f}", showarrow=True,
                       arrowhead=2, arrowcolor="#FF4FD8", ax=-60, ay=-40,
                       font=dict(color="#FF4FD8", size=14))
    fig.add_annotation(x=lo_i, y=lo_v, text=f"Low ${lo_v:,.0f}", showarrow=True,
                       arrowhead=2, arrowcolor="#00B8FF", ax=50, ay=40,
                       font=dict(color="#00B8FF", size=14))
    move_pct = (float(close.iloc[-1]) - lo_v) / lo_v * 100
    fig.add_annotation(x=gd.index[-1], y=float(close.iloc[-1]),
                       text=f"${close.iloc[-1]:,.0f}  ({move_pct:+.1f}% from low)",
                       showarrow=True, arrowhead=2, arrowcolor=UP, ax=-110, ay=-45,
                       bgcolor="rgba(0,230,118,.18)", bordercolor=UP, borderpad=5,
                       font=dict(color="#FFFFFF", size=13))

    fig.update_layout(
        height=520,
        margin=dict(l=70, r=80, t=30, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,.35)",
        font=dict(color="#FFFFFF", size=12, family="Public Sans, sans-serif"),
        yaxis=dict(title="Gold ($/oz)", side="right", gridcolor="#2A2418", zeroline=False),
        yaxis2=dict(title="Dollar / Yield", overlaying="y", side="left",
                    showgrid=False, zeroline=False),
        xaxis=dict(gridcolor="#2A2418", rangeslider=dict(visible=False),
                   rangebreaks=[dict(bounds=["sat", "mon"])]),
        legend=dict(orientation="h", y=1.08, font=dict(color="#FFFFFF", size=13)),
    )
    st.plotly_chart(fig, width="stretch", theme=None)

    # ---------- Correlation ----------
    st.subheader("How closely do they move together?")
    moves = pd.DataFrame({"gold": close, "Dollar Index": compare["Dollar Index"],
                          "10Y Yield (%)": compare["10Y Yield (%)"]}).pct_change().dropna()
    corr = moves.corr()["gold"]
    k1, k2 = st.columns(2)
    k1.metric("Dollar Index vs gold", f"{corr['Dollar Index']:.2f}")
    k2.metric("10Y Yield vs gold", f"{corr['10Y Yield (%)']:.2f}")
    st.caption("Daily moves over the last 6 months. -1 means they move in opposite directions, +1 means the same direction.")


def page_news():

    st.subheader("🤖 AI daily summary")
    gold_now, gold_prev = last_two("gold")
    silver_now, silver_prev = last_two("silver")
    gold_move = gold_now - gold_prev
    dollar_move = dollar_now - dollar_prev
    try:
        headlines = load_news()
    except Exception:
        headlines = []

    facts = "\n".join([
        f"Gold: ${gold_now:,.2f} per oz, {gold_move:+,.2f} ({(gold_now / gold_prev - 1) * 100:+.2f}%) vs previous close",
        f"Silver: ${silver_now:,.2f} per oz, {(silver_now / silver_prev - 1) * 100:+.2f}% vs previous close",
        f"Dollar Index: {dollar_now:.2f} ({dollar_move:+.2f})",
        f"10-year Treasury yield: {y_now:.2f}% ({y_now - y_prev:+.2f})",
        f"US inflation (CPI, yearly): {inflation_cpi:.1f}%",
        "Recent headlines:",
        *[f"- {h['title']} ({h['source']})" for h in headlines[:8]],
    ])

    summary_text = None
    if not live:
        summary_note = "The AI summary needs live prices, so it is off while the page shows sample data."
    else:
        try:
            summary_text = ai_summary(pd.Timestamp.now(tz="America/Los_Angeles").strftime("%A, %B %d, %Y"), facts)
            summary_note = None
        except ImportError:
            summary_note = "To turn on the AI summary, install the AI library:  python -m pip install anthropic"
        except Exception as exc:
            name = type(exc).__name__
            if "Authentication" in name or "api_key" in str(exc).lower():
                k = _clean_key()
                found = (f"a key with {len(k)} characters starting with '{k[:7]}' was found"
                         if k else "no key was found in the app's Secrets")
                summary_note = (f"The AI summary is not available right now ({name}; {found}; "
                                f"{str(exc)[:160]}).")
            else:
                cause = f" / {type(exc.__cause__).__name__}: {str(exc.__cause__)[:150]}" if exc.__cause__ else ""
                summary_note = (f"The AI summary could not be written right now ({name}: {str(exc)[:150]}{cause}). "
                                "Please try again later.")

    if summary_text:
        st.info(summary_text.replace("$", "\\$"))
        st.caption(f"Written by AI ({AI_MODEL}) from today's prices and headlines. "
                   "It can make mistakes. Educational only, not financial advice.")
    else:
        direction = "rose" if gold_move > 0 else "fell"
        dollar_dir = "strengthened" if dollar_move > 0 else "weakened"
        st.info(
            f"Gold {direction} ${abs(gold_move):,.2f} from the last close while the dollar {dollar_dir}. "
            "Gold often moves opposite the dollar and Treasury yields, because a weaker "
            "dollar and lower yields make gold cheaper to hold. Educational only, not financial advice."
        )
        if summary_note:
            st.caption(summary_note)

    # ---------- Gold news ----------
    st.subheader("📰 Gold news")
    TAG_COLORS = [("fed", "#00B8FF", "FED"), ("rate", "#00B8FF", "RATES"), ("dollar", "#00E676", "DOLLAR"),
                  ("silver", "#C0C0C0", "SILVER"), ("inflation", "#FF9F1C", "INFLATION"), ("gold", "#F5D76E", "GOLD")]
    try:
        news = load_news()
    except Exception:
        news = []
    if not news:
        st.caption("Headlines could not be loaded right now. Press Refresh prices to try again.")
    else:
        now_utc = pd.Timestamp.now(tz="UTC")
        n1, n2 = st.columns(2)
        for i, item in enumerate(news):
            low_title = item["title"].lower()
            tags = "".join(f'<span class="mh-tag" style="background:{c}">{t}</span>'
                           for k, c, t in TAG_COLORS if k in low_title)
            ago = ""
            if item["when"] is not None:
                mins = int((now_utc - pd.Timestamp(item["when"]).tz_convert("UTC")).total_seconds() // 60)
                ago = f"{mins} min ago" if mins < 60 else (f"{mins // 60} hr ago" if mins < 1440 else f"{mins // 1440} days ago")
            meta = " · ".join(x for x in (html.escape(item["source"]), ago) if x)
            card = (f'<div class="mh-news"><div class="mh-title">{tags}'
                    f'<a href="{html.escape(item["link"], quote=True)}" target="_blank" rel="noopener">'
                    f'{html.escape(item["title"])}</a></div>'
                    f'<div class="mh-meta">{meta}</div></div>')
            (n1 if i % 2 == 0 else n2).markdown(card, unsafe_allow_html=True)
        st.caption("Headlines from Google News. Click a headline to read the full story.")

def page_history():
    st.subheader("📜 Gold history: the last 25 years")
    g = daily["gold"]["Close"]
    start = g.index[-1] - pd.DateOffset(years=25)
    g25 = g.loc[start:]
    if len(g25) < 500:
        st.info("Long-term history needs live data. It will appear when live prices are available.")
        return

    first, last = float(g25.iloc[0]), float(g25.iloc[-1])
    years = (g25.index[-1] - g25.index[0]).days / 365.25
    cagr = ((last / first) ** (1 / years) - 1) * 100
    full = g25.loc[str(g25.index[0].year + 1):]          # skip the partial first year
    yearly = full.groupby(full.index.year).agg(["first", "last"])
    yearly_pct = (yearly["last"] / yearly["first"] - 1) * 100
    best_y, worst_y = int(yearly_pct.idxmax()), int(yearly_pct.idxmin())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Price in {g25.index[0]:%b %Y}", f"${first:,.0f}")
    c2.metric("Price today", f"${last:,.0f}", f"{(last / first - 1) * 100:+,.0f}% total")
    c3.metric("Average yearly gain", f"{cagr:.1f}%")
    c4.metric("Best / worst year", f"{best_y}: {yearly_pct[best_y]:+.0f}%",
              f"{worst_y}: {yearly_pct[worst_y]:+.0f}%", delta_color="off")

    # (date, label, arrow x-offset, arrow y-offset) - offsets keep labels from overlapping
    events = [
        ("2008-09-15", "2008 financial crisis<br>(Lehman Brothers fails)", 0, -70),
        ("2011-09-06", "2011 record high<br>(debt crisis fears)", -70, -60),
        ("2013-04-15", "April 2013 crash", 40, -150),
        ("2015-12-17", "First Fed rate hike<br>since 2006", 0, -80),
        ("2020-08-06", "COVID: gold tops $2,000", -60, -110),
        ("2022-03-08", "Russia invades Ukraine", 40, -70),
        ("2025-03-14", "Gold tops $3,000", -120, -20),
        ("2025-10-08", "Gold tops $4,000", -130, 10),
    ]
    fig = go.Figure(go.Scatter(x=g25.index, y=g25.values, mode="lines", name="Gold ($/oz)",
                               line=dict(color=GOLD_DEEP, width=2), fill="tozeroy",
                               fillcolor="rgba(212,175,55,.12)",
                               hovertemplate="%{x|%b %d, %Y}<br>$%{y:,.0f}<extra></extra>"))
    for day, label, dx, dy in events:
        d = pd.Timestamp(day)
        if d < g25.index[0] or d > g25.index[-1]:
            continue
        price = float(g25.loc[:d].iloc[-1])
        fig.add_annotation(x=d, y=price, text=label, showarrow=True, arrowhead=2,
                           arrowcolor="#FFFFFF", ax=dx, ay=dy,
                           font=dict(color="#FFFFFF", size=11),
                           bgcolor="rgba(0,0,0,.65)", bordercolor=GOLD_DEEP, borderpad=4)
    top_i = g25.idxmax()
    fig.add_annotation(x=top_i, y=float(g25.max()), text=f"Highest close ${g25.max():,.0f}<br>{top_i:%b %Y}",
                       showarrow=True, arrowhead=2, arrowcolor=UP, ax=-150, ay=-25,
                       font=dict(color=UP, size=11), bgcolor="rgba(0,0,0,.65)", bordercolor=UP, borderpad=4)
    fig.update_layout(height=560, margin=dict(l=20, r=70, t=30, b=40), showlegend=False,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,.35)",
                      font=dict(color="#FFFFFF", size=12, family="Public Sans, sans-serif"),
                      xaxis=dict(gridcolor="#2A2418"),
                      yaxis=dict(title="Gold ($/oz)", side="right", gridcolor="#2A2418", tickprefix="$"))
    st.plotly_chart(fig, width="stretch", theme=None)
    st.caption("COMEX gold futures, daily closing price. Event dates are approximate.")

    st.subheader("Gold's gain or loss each year")
    colors = [UP if v >= 0 else DOWN for v in yearly_pct.values]
    labels = [str(y) + (" (so far)" if y == g25.index[-1].year else "") for y in yearly_pct.index]
    bar = go.Figure(go.Bar(x=labels, y=yearly_pct.values, marker_color=colors,
                           text=[f"{v:+.0f}%" for v in yearly_pct.values], textposition="outside",
                           textfont=dict(color="#FFFFFF", size=11),
                           hovertemplate="%{x}: %{y:+.1f}%<extra></extra>"))
    bar.update_layout(height=420, margin=dict(l=55, r=20, t=30, b=80), showlegend=False,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,.35)",
                      font=dict(color="#FFFFFF", size=11, family="Public Sans, sans-serif"),
                      xaxis=dict(tickangle=-45, type="category"),
                      yaxis=dict(gridcolor="#2A2418", ticksuffix="%",
                                 range=[min(yearly_pct.min(), 0) * 1.3 - 5, max(yearly_pct.max(), 0) * 1.2 + 5]))
    st.plotly_chart(bar, width="stretch", theme=None)
    st.caption("Change from the first to the last trading day of each year. Past performance does not predict the future.")


LESSONS = [
    ("What is the gold price?",
     "The price you see is usually for one troy ounce of gold in US dollars. A troy ounce is about 31.1 grams, "
     "a little heavier than a regular ounce. This app shows COMEX gold futures, which trade almost around the clock "
     "and stay very close to the spot price."),
    ("Spot price vs. what you pay",
     "The spot price is the market price for large amounts of gold. When you buy coins or bars, dealers add a premium "
     "on top for minting, shipping and their business. When you sell, you usually get a bit less than spot."),
    ("Why the dollar matters",
     "Gold is priced in US dollars. When the dollar gets stronger, gold costs more for buyers using other currencies, "
     "so demand can fall and the price often slips. A weaker dollar usually helps gold."),
    ("Why interest rates matter",
     "Gold pays no interest. When Treasury yields rise, savers can earn more from bonds, so holding gold costs more "
     "in missed interest. When rates fall, gold often looks more attractive. Federal Reserve meetings can move gold a lot."),
    ("Why inflation matters",
     "Many people buy gold to protect their savings when prices are rising fast. Gold has kept its value over very long "
     "periods, but in the short term it does not always rise with inflation."),
    ("Gold as a safe haven",
     "In wars, financial crises and times of fear, investors often move money into gold. That is why gold jumped in "
     "2008, 2020 and 2022. See the Gold History page for these moments."),
    ("The gold / silver ratio",
     "This number tells you how many ounces of silver it takes to buy one ounce of gold. A high ratio means silver is "
     "cheap compared with gold; a low ratio means silver is expensive compared with gold."),
    ("How to read a candlestick chart",
     "Each candle is one day. Green means the price closed higher than it opened, red means it closed lower. The thin "
     "lines (wicks) show the highest and lowest prices of the day."),
    ("What are the Fibonacci lines?",
     "Traders draw lines at 23.6%, 38.2%, 50% and 61.8% of the distance between a recent high and low. Many traders "
     "watch these levels for possible pauses or turns. They are a tool, not a promise."),
    ("Ways people own gold",
     "Physical coins and bars, gold funds (ETFs) that track the price, shares of mining companies, and futures. Each "
     "has different costs and risks. Mining shares can move much more than gold itself."),
]


def page_learn():
    st.subheader("📚 Learn gold")
    st.caption("Simple guides for beginners. Click a topic to open it.")
    left, right = st.columns(2)
    for i, (title, body) in enumerate(LESSONS):
        with (left if i % 2 == 0 else right).expander(title):
            st.write(body)
    st.info("MH Gold Radar is for learning only. It does not tell you to buy or sell. "
            "Talk to a licensed financial professional before making investment decisions.")



# ---------- Header (every page) ----------
st.title("🪙 MH Gold Radar")
if live:
    st.caption(f"Gold market AI, explained simply. LIVE DATA - Yahoo Finance (delayed ~15 min), "
               f"updated {pd.Timestamp.now(tz='America/Los_Angeles'):%b %d, %Y %I:%M %p} PT.")
else:
    st.caption("Gold market AI, explained simply. SAMPLE DATA - live prices could not be reached.")
    st.warning("Live prices are not available right now, so you are seeing sample numbers. "
               "If you haven't yet, install the price library with:  python -m pip install yfinance")

if st.button("🔄 Refresh prices"):
    # Refresh prices and news only. The AI summary is written once a day and is
    # never re-written by this button, so visitors can't run up the AI bill.
    load_live.clear()
    load_news.clear()
    st.rerun()

pages = [
    st.Page(page_dashboard, title="Dashboard", icon="🏠", default=True),
    st.Page(page_moves, title="What Moves Gold", icon="📈", url_path="what-moves-gold"),
    st.Page(page_news, title="News & AI Summary", icon="📰", url_path="news"),
    st.Page(page_history, title="Gold History", icon="📜", url_path="history"),
    st.Page(page_learn, title="Learn Gold", icon="📚", url_path="learn"),
]
st.navigation(pages, position="top").run()

st.divider()
st.caption("MH Gold Radar is for education only and is not investment advice. "
           "Prices are COMEX gold and silver futures, which can differ slightly from spot prices.")
