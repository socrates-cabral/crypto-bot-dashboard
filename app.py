import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
import json, os, requests
from datetime import datetime, timezone

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

PAR = "BTC_USDT"
REFRESH_SEC = 30
BASE_DIR = Path(__file__).parent

# ── Paleta ────────────────────────────────────────────────────────────────────
BG        = "#0f172a"
BG_CARD   = "#1e293b"
BG_CARD2  = "#162032"
BORDER    = "#334155"
GOLD      = "#f59e0b"
GOLD_D    = "#d97706"
GREEN     = "#10b981"
GREEN_D   = "#059669"
RED       = "#f43f5e"
BLUE      = "#3b82f6"
TEXT      = "#e2e8f0"
TEXT_SEC  = "#94a3b8"
TEXT_MUTED= "#64748b"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Crypto Bot — BTC Grid",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS global ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

.stApp {{
    background-color: {BG};
    font-family: 'Inter', 'Segoe UI', sans-serif;
    color: {TEXT};
}}
section[data-testid="stSidebar"] {{ background-color: #0a1020; border-right: 1px solid {BORDER}; }}

/* Ocultar elementos Streamlit innecesarios */
#MainMenu, footer, header {{ visibility: hidden; }}
.block-container {{ padding-top: 1.5rem; padding-bottom: 2rem; }}

/* ── KPI Cards ── */
.kpi-card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 16px 20px;
    text-align: center;
}}
.kpi-card.gold  {{ border-top: 3px solid {GOLD}; }}
.kpi-card.green {{ border-top: 3px solid {GREEN}; }}
.kpi-card.red   {{ border-top: 3px solid {RED}; }}
.kpi-card.blue  {{ border-top: 3px solid {BLUE}; }}
.kpi-card.muted {{ border-top: 3px solid {BORDER}; }}
.kpi-label {{
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {TEXT_MUTED};
    margin-bottom: 6px;
}}
.kpi-value {{
    font-size: 1.7rem;
    font-weight: 800;
    line-height: 1.1;
    color: {TEXT};
}}
.kpi-sub {{
    font-size: 0.75rem;
    color: {TEXT_SEC};
    margin-top: 4px;
}}

/* ── Section headers ── */
.section-title {{
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: {TEXT_MUTED};
    margin: 24px 0 12px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid {BORDER};
}}

/* ── Trade badge ── */
.badge-buy  {{ background:#064e3b; color:#34d399; border:1px solid #065f46;
               padding:2px 10px; border-radius:20px; font-size:0.7rem; font-weight:700; }}
.badge-sell {{ background:#4c0519; color:#fb7185; border:1px solid #9f1239;
               padding:2px 10px; border-radius:20px; font-size:0.7rem; font-weight:700; }}

/* ── Live badge ── */
.live-badge {{
    display:inline-block;
    background:#064e3b; color:#34d399;
    border:1px solid #065f46;
    padding:3px 10px; border-radius:20px;
    font-size:0.7rem; font-weight:700;
    animation: pulse 2s infinite;
}}
@keyframes pulse {{
    0%,100% {{ opacity:1; }} 50% {{ opacity:0.6; }}
}}

/* ── Paper badge ── */
.paper-badge {{
    display:inline-block;
    background:#1c1917; color:{GOLD};
    border:1px solid {GOLD_D};
    padding:3px 12px; border-radius:20px;
    font-size:0.7rem; font-weight:700;
}}

/* ── Range bar ── */
.range-bar-outer {{
    background: {BORDER};
    border-radius: 6px;
    height: 8px;
    margin: 6px 0;
    position: relative;
    overflow: hidden;
}}
.range-bar-inner {{
    height: 8px;
    border-radius: 6px;
    background: linear-gradient(90deg, {GOLD}, {GREEN});
    transition: width 0.5s;
}}

/* ── Tables ── */
.stDataFrame {{ border: 1px solid {BORDER} !important; border-radius: 8px !important; }}
[data-testid="stDataFrameResizable"] {{ background: {BG_CARD} !important; }}

/* ── Divider ── */
hr {{ border-color: {BORDER} !important; margin: 16px 0 !important; }}
</style>
""", unsafe_allow_html=True)


# ── Data helpers ──────────────────────────────────────────────────────────────

def _sb_client():
    url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


@st.cache_data(ttl=REFRESH_SEC)
def load_estado() -> dict:
    client = _sb_client()
    if client:
        try:
            r = client.table("crypto_grid_state").select("estado").eq("par", PAR).single().execute()
            if r.data:
                return r.data["estado"]
        except Exception:
            pass
    if (BASE_DIR / "estado_grid.json").exists():
        with open(BASE_DIR / "estado_grid.json", encoding="utf-8") as f:
            return json.load(f)
    return {}


@st.cache_data(ttl=REFRESH_SEC)
def load_historico() -> list[dict]:
    client = _sb_client()
    if client:
        try:
            r = (client.table("crypto_operaciones")
                 .select("tipo,precio,qty,pnl,timestamp")
                 .eq("par", PAR).order("timestamp", desc=False).limit(500).execute())
            return r.data or []
        except Exception:
            pass
    p = BASE_DIR / "data" / "historico_operaciones.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


@st.cache_data(ttl=REFRESH_SEC)
def get_btc_price() -> float:
    try:
        r = requests.get(
            "https://api.crypto.com/exchange/v1/public/get-tickers",
            params={"instrument_name": PAR}, timeout=10)
        return float(r.json()["result"]["data"][0].get("last") or 0)
    except Exception:
        return 0.0


@st.cache_data(ttl=120)
def get_candles_1h(limit: int = 48) -> list[dict]:
    """Últimas 48 velas 1H para el mini-chart."""
    try:
        r = requests.get(
            "https://api.crypto.com/exchange/v1/public/get-candlestick",
            params={"instrument_name": PAR, "timeframe": "1h", "count": limit},
            timeout=15)
        data = r.json()["result"]["data"]
        candles = []
        for c in data:
            ts = c.get("t") or c.get("timestamp", 0)
            candles.append({
                "ts":    int(ts) // 1000,
                "open":  float(c.get("o") or 0),
                "high":  float(c.get("h") or 0),
                "low":   float(c.get("l") or 0),
                "close": float(c.get("c") or 0),
            })
        return sorted(candles, key=lambda x: x["ts"])
    except Exception:
        return []


# ── Load data ─────────────────────────────────────────────────────────────────
estado    = load_estado()
historico = load_historico()
precio    = get_btc_price() or estado.get("precio_ultimo", 0)
candles   = get_candles_1h()

if not estado:
    st.markdown(f"""
    <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:12px;
                padding:40px;text-align:center;margin-top:40px;">
      <div style="font-size:3rem;">₿</div>
      <h2 style="color:{GOLD};">Crypto Bot sin datos</h2>
      <p style="color:{TEXT_SEC};">El bot no ha corrido aún o Supabase no está configurado.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

niveles      = estado.get("niveles", [])
pnl_total    = estado.get("pnl_realizado_usdt", 0)
capital      = estado.get("capital_usdt", 1000)
grid_lower   = estado.get("grid_lower", 0)
grid_upper   = estado.get("grid_upper", 0)
open_niveles = [n for n in niveles if n["estado"] != "idle"]
ultima_act   = estado.get("ultima_actualizacion", "")

roi_pct    = (pnl_total / capital) * 100 if capital else 0
sells      = [t for t in historico if t["tipo"] == "SELL"]
buys       = [t for t in historico if t["tipo"] == "BUY"]
pnl_color  = GREEN if pnl_total >= 0 else RED
dentro     = grid_lower <= precio <= grid_upper

# Posición del precio en el grid (0-100%)
rango = grid_upper - grid_lower
precio_pct = max(0, min(100, ((precio - grid_lower) / rango * 100))) if rango else 50

# Unrealized PnL
unrealized = sum((precio - n["precio"]) * n["btc_qty"] for n in open_niveles)

# ── Header ────────────────────────────────────────────────────────────────────
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown(f"""
    <h1 style="font-size:1.8rem;font-weight:800;color:{GOLD};margin:0;letter-spacing:-0.5px;">
      ₿ Crypto Bot — Grid Trading
    </h1>
    <p style="color:{TEXT_SEC};font-size:0.85rem;margin:4px 0 0 0;">
      BTC/USDT · Estrategia Grid + Filtro EMA 200
    </p>
    """, unsafe_allow_html=True)
with col_h2:
    st.markdown(f"""
    <div style="text-align:right;padding-top:8px;">
      <span class="paper-badge">PAPER TRADING</span>&nbsp;
      <span class="live-badge">● LIVE</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ── KPI row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5, k6 = st.columns(6)

with k1:
    st.markdown(f"""
    <div class="kpi-card gold">
      <div class="kpi-label">BTC Precio</div>
      <div class="kpi-value" style="color:{GOLD};">${precio:,.0f}</div>
      <div class="kpi-sub">USD en tiempo real</div>
    </div>""", unsafe_allow_html=True)

with k2:
    sign = "+" if pnl_total >= 0 else ""
    st.markdown(f"""
    <div class="kpi-card {'green' if pnl_total >= 0 else 'red'}">
      <div class="kpi-label">PnL Realizado</div>
      <div class="kpi-value" style="color:{'#10b981' if pnl_total >= 0 else '#f43f5e'};">
        {sign}{pnl_total:.4f}
      </div>
      <div class="kpi-sub">USDT</div>
    </div>""", unsafe_allow_html=True)

with k3:
    sign = "+" if roi_pct >= 0 else ""
    st.markdown(f"""
    <div class="kpi-card {'green' if roi_pct >= 0 else 'red'}">
      <div class="kpi-label">ROI</div>
      <div class="kpi-value" style="color:{'#10b981' if roi_pct >= 0 else '#f43f5e'};">
        {sign}{roi_pct:.2f}%
      </div>
      <div class="kpi-sub">sobre ${capital:,.0f} capital</div>
    </div>""", unsafe_allow_html=True)

with k4:
    sign_u = "+" if unrealized >= 0 else ""
    st.markdown(f"""
    <div class="kpi-card {'green' if unrealized >= 0 else 'red'}">
      <div class="kpi-label">PnL No Real.</div>
      <div class="kpi-value" style="color:{'#10b981' if unrealized >= 0 else '#f43f5e'};font-size:1.4rem;">
        {sign_u}{unrealized:.4f}
      </div>
      <div class="kpi-sub">{len(open_niveles)} posiciones abiertas</div>
    </div>""", unsafe_allow_html=True)

with k5:
    st.markdown(f"""
    <div class="kpi-card blue">
      <div class="kpi-label">Operaciones</div>
      <div class="kpi-value" style="color:{BLUE};">{len(historico)}</div>
      <div class="kpi-sub">{len(buys)} compras · {len(sells)} ventas</div>
    </div>""", unsafe_allow_html=True)

with k6:
    rng_color = "green" if dentro else "red"
    rng_txt   = "Dentro del grid" if dentro else "FUERA DEL GRID"
    rng_icon  = "✓" if dentro else "⚠"
    st.markdown(f"""
    <div class="kpi-card {rng_color}">
      <div class="kpi-label">Rango Grid</div>
      <div class="kpi-value" style="color:{TEXT};font-size:1.2rem;">
        ${grid_lower//1000}K–${grid_upper//1000}K
      </div>
      <div class="kpi-sub" style="color:{'#10b981' if dentro else '#f43f5e'};">
        {rng_icon} {rng_txt}
      </div>
    </div>""", unsafe_allow_html=True)

# Barra posición precio en el grid
st.markdown(f"""
<div style="margin:16px 0 4px 0;">
  <div style="display:flex;justify-content:space-between;
              font-size:0.7rem;color:{TEXT_MUTED};margin-bottom:4px;">
    <span>Grid inferior ${grid_lower:,}</span>
    <span style="color:{GOLD};font-weight:600;">BTC ${precio:,.0f} ({precio_pct:.0f}%)</span>
    <span>Grid superior ${grid_upper:,}</span>
  </div>
  <div class="range-bar-outer">
    <div class="range-bar-inner" style="width:{precio_pct}%;"></div>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ── Gráfico + Posiciones ──────────────────────────────────────────────────────
col_chart, col_pos = st.columns([3, 2])

with col_chart:
    st.markdown(f'<div class="section-title">Precio BTC vs Grid (últimas 48h)</div>', unsafe_allow_html=True)

    fig = go.Figure()

    # Velas 1H
    if candles:
        ts_labels = [datetime.fromtimestamp(c["ts"]).strftime("%d/%m %H:%M") for c in candles]
        fig.add_trace(go.Candlestick(
            x=list(range(len(candles))),
            open=[c["open"]  for c in candles],
            high=[c["high"]  for c in candles],
            low= [c["low"]   for c in candles],
            close=[c["close"] for c in candles],
            name="BTC/USDT",
            increasing_line_color=GREEN,
            decreasing_line_color=RED,
            increasing_fillcolor=GREEN,
            decreasing_fillcolor=RED,
            showlegend=False,
        ))
        x_range = [0, len(candles) - 1]
    else:
        x_range = [0, 1]

    # Niveles del grid
    for nivel in niveles:
        p = nivel["precio"]
        is_open = nivel["estado"] == "buy_open"
        fig.add_shape(type="line",
            x0=x_range[0], x1=x_range[1], y0=p, y1=p,
            line=dict(color=RED if is_open else "#334155",
                      width=1.5 if is_open else 0.7,
                      dash="solid" if is_open else "dot"),
        )
        if is_open:
            fig.add_annotation(
                x=x_range[1], y=p,
                text=f" ${p:,.0f} ●",
                showarrow=False, xanchor="left",
                font=dict(color=RED, size=10, family="Inter"),
            )

    # Precio actual
    fig.add_hline(y=precio,
        line=dict(color=GOLD, width=2, dash="solid"),
        annotation_text=f"  ${precio:,.0f}",
        annotation_font=dict(color=GOLD, size=11),
        annotation_position="right",
    )

    # Banda grid
    fig.add_hrect(y0=grid_lower, y1=grid_upper,
        fillcolor="rgba(59,130,246,0.04)", line_width=0)

    fig.update_layout(
        height=380,
        paper_bgcolor=BG_CARD,
        plot_bgcolor=BG_CARD,
        margin=dict(l=10, r=90, t=10, b=30),
        xaxis=dict(
            showgrid=False, showticklabels=False,
            rangeslider=dict(visible=False),
            linecolor=BORDER,
        ),
        yaxis=dict(
            tickformat="$,.0f",
            tickfont=dict(color=TEXT_MUTED, size=10),
            gridcolor="#1e293b",
            linecolor=BORDER,
        ),
        font=dict(family="Inter, Segoe UI, sans-serif"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    if ultima_act:
        try:
            dt = datetime.fromisoformat(ultima_act)
            st.markdown(f'<p style="font-size:0.7rem;color:{TEXT_MUTED};margin:-10px 0 0 0;">'
                        f'Bot actualizado: {dt.strftime("%Y-%m-%d %H:%M:%S UTC")}</p>',
                        unsafe_allow_html=True)
        except Exception:
            pass

with col_pos:
    st.markdown(f'<div class="section-title">Posiciones Abiertas ({len(open_niveles)})</div>',
                unsafe_allow_html=True)

    if open_niveles:
        for n in sorted(open_niveles, key=lambda x: x["precio"], reverse=True):
            pnl_n = (precio - n["precio"]) * n["btc_qty"]
            pnl_col = GREEN if pnl_n >= 0 else RED
            sign_n = "+" if pnl_n >= 0 else ""
            st.markdown(f"""
            <div style="background:{BG_CARD2};border:1px solid {BORDER};border-left:3px solid {RED};
                        border-radius:8px;padding:10px 14px;margin-bottom:8px;
                        display:flex;justify-content:space-between;align-items:center;">
              <div>
                <div style="font-weight:700;color:{TEXT};font-size:0.9rem;">${n['precio']:,.0f}</div>
                <div style="font-size:0.72rem;color:{TEXT_MUTED};">{n['btc_qty']:.8f} BTC</div>
              </div>
              <div style="text-align:right;">
                <div style="font-weight:700;color:{pnl_col};font-size:0.9rem;">
                  {sign_n}{pnl_n:.4f} USDT
                </div>
                <div style="font-size:0.7rem;color:{TEXT_MUTED};">no realizado</div>
              </div>
            </div>""", unsafe_allow_html=True)

        total_u_color = GREEN if unrealized >= 0 else RED
        sign_u = "+" if unrealized >= 0 else ""
        st.markdown(f"""
        <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;
                    padding:10px 14px;margin-top:4px;text-align:center;">
          <span style="font-size:0.7rem;color:{TEXT_MUTED};">TOTAL NO REALIZADO&nbsp;&nbsp;</span>
          <span style="font-weight:800;color:{total_u_color};">
            {sign_u}{unrealized:.4f} USDT
          </span>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background:{BG_CARD2};border:1px solid {BORDER};border-radius:8px;
                    padding:24px;text-align:center;color:{TEXT_MUTED};">
          Sin posiciones abiertas
        </div>""", unsafe_allow_html=True)

    # Config resumida
    st.markdown(f'<div class="section-title" style="margin-top:20px;">Configuración</div>',
                unsafe_allow_html=True)
    cfg = [
        ("Par", estado.get("par", "—")),
        ("Capital", f"${capital:,.0f} USDT"),
        ("Niveles", f"{estado.get('grid_levels','—')} (step ${estado.get('nivel_step',0):,.0f})"),
        ("Capital/nivel", f"${estado.get('capital_por_nivel',0):.2f} USDT"),
        ("Rango", f"${grid_lower:,} – ${grid_upper:,}"),
    ]
    for label, val in cfg:
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;padding:5px 0;
                    border-bottom:1px solid {BG_CARD2};">
          <span style="font-size:0.78rem;color:{TEXT_MUTED};">{label}</span>
          <span style="font-size:0.78rem;font-weight:600;color:{TEXT};">{val}</span>
        </div>""", unsafe_allow_html=True)

# ── Historial ─────────────────────────────────────────────────────────────────
st.markdown(f'<div class="section-title">Historial de Operaciones</div>', unsafe_allow_html=True)

if historico:
    hist_rev = list(reversed(historico))
    rows_html = ""
    for t in hist_rev[:50]:
        tipo  = t["tipo"]
        badge = f'<span class="badge-{"buy" if tipo=="BUY" else "sell"}">{tipo}</span>'
        precio_t = float(t.get("precio", 0))
        qty_t    = float(t.get("qty", 0))
        pnl_t    = t.get("pnl")
        pnl_str  = f'<span style="color:{GREEN};">+{float(pnl_t):.4f}</span>' if pnl_t else "—"
        try:
            ts = datetime.fromisoformat(str(t.get("timestamp",""))).strftime("%d/%m %H:%M")
        except Exception:
            ts = str(t.get("timestamp",""))[:16]
        rows_html += f"""
        <tr style="border-bottom:1px solid {BORDER};">
          <td style="padding:8px 12px;color:{TEXT_MUTED};font-size:0.78rem;">{ts}</td>
          <td style="padding:8px 12px;">{badge}</td>
          <td style="padding:8px 12px;font-weight:600;color:{TEXT};">${precio_t:,.0f}</td>
          <td style="padding:8px 12px;color:{TEXT_SEC};font-size:0.8rem;">{qty_t:.8f}</td>
          <td style="padding:8px 12px;font-size:0.8rem;">{pnl_str}</td>
        </tr>"""

    st.markdown(f"""
    <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:10px;overflow:hidden;">
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:{BG_CARD2};">
            <th style="padding:10px 12px;text-align:left;font-size:0.7rem;
                       text-transform:uppercase;letter-spacing:0.08em;color:{TEXT_MUTED};">Fecha UTC</th>
            <th style="padding:10px 12px;text-align:left;font-size:0.7rem;
                       text-transform:uppercase;letter-spacing:0.08em;color:{TEXT_MUTED};">Tipo</th>
            <th style="padding:10px 12px;text-align:left;font-size:0.7rem;
                       text-transform:uppercase;letter-spacing:0.08em;color:{TEXT_MUTED};">Precio</th>
            <th style="padding:10px 12px;text-align:left;font-size:0.7rem;
                       text-transform:uppercase;letter-spacing:0.08em;color:{TEXT_MUTED};">BTC Qty</th>
            <th style="padding:10px 12px;text-align:left;font-size:0.7rem;
                       text-transform:uppercase;letter-spacing:0.08em;color:{TEXT_MUTED};">PnL (USDT)</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    """, unsafe_allow_html=True)
    if len(historico) > 50:
        st.markdown(f'<p style="font-size:0.72rem;color:{TEXT_MUTED};margin-top:6px;">'
                    f'Mostrando últimas 50 de {len(historico)} operaciones</p>',
                    unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:10px;
                padding:32px;text-align:center;color:{TEXT_MUTED};">
      Sin operaciones registradas aún.
    </div>""", unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:center;">
  <span style="font-size:0.7rem;color:{TEXT_MUTED};">
    Auto-refresh cada {REFRESH_SEC}s · Datos: Crypto.com API + Supabase
  </span>
  <span style="font-size:0.7rem;color:{TEXT_MUTED};">
    Socrates Labs · {datetime.now().strftime('%Y')}
  </span>
</div>
<meta http-equiv='refresh' content='{REFRESH_SEC}'>
""", unsafe_allow_html=True)
