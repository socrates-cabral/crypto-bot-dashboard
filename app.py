import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
import json, os, requests
from datetime import datetime, timezone

import streamlit as st
import plotly.graph_objects as go

PARES = ["BTC_USDT", "ETH_USDT"]
REFRESH_SEC = 30
BASE_DIR = Path(__file__).parent

COIN_ICON  = {"BTC_USDT": "₿", "ETH_USDT": "Ξ"}
COIN_COLOR = {"BTC_USDT": "#f59e0b", "ETH_USDT": "#818cf8"}

BG       = "#0f172a"
BG_CARD  = "#1e293b"
BG_CARD2 = "#162032"
BORDER   = "#334155"
GREEN    = "#10b981"
RED      = "#f43f5e"
BLUE     = "#3b82f6"
TEXT     = "#e2e8f0"
TEXT_SEC = "#94a3b8"
TEXT_M   = "#64748b"

st.set_page_config(page_title="Crypto Bot — Grid Trading", page_icon="₿", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
.stApp {{ background:{BG}; font-family:'Inter','Segoe UI',sans-serif; color:{TEXT}; }}
#MainMenu, footer, header {{ visibility:hidden; }}
.block-container {{ padding-top:1.5rem; padding-bottom:2rem; }}
section[data-testid="stSidebar"] {{ background:#0a1020; border-right:1px solid {BORDER}; }}
.kpi-card {{ background:{BG_CARD}; border:1px solid {BORDER}; border-radius:12px;
             padding:14px 18px; text-align:center; height:100%; }}
.kpi-label {{ font-size:.68rem; font-weight:700; text-transform:uppercase;
              letter-spacing:.08em; color:{TEXT_M}; margin-bottom:5px; }}
.kpi-value {{ font-size:1.55rem; font-weight:800; line-height:1.1; color:{TEXT}; }}
.kpi-sub   {{ font-size:.72rem; color:{TEXT_SEC}; margin-top:3px; }}
.sec-title {{ font-size:.72rem; font-weight:700; text-transform:uppercase;
              letter-spacing:.1em; color:{TEXT_M}; margin:20px 0 10px;
              padding-bottom:5px; border-bottom:1px solid {BORDER}; }}
.badge-buy  {{ background:#064e3b; color:#34d399; border:1px solid #065f46;
               padding:2px 9px; border-radius:20px; font-size:.68rem; font-weight:700; }}
.badge-sell {{ background:#4c0519; color:#fb7185; border:1px solid #9f1239;
               padding:2px 9px; border-radius:20px; font-size:.68rem; font-weight:700; }}
.live-badge {{ display:inline-block; background:#064e3b; color:#34d399;
               border:1px solid #065f46; padding:3px 10px; border-radius:20px;
               font-size:.68rem; font-weight:700; animation:pulse 2s infinite; }}
.paper-badge {{ display:inline-block; background:#1c1917; border:1px solid #d97706;
                padding:3px 12px; border-radius:20px; font-size:.68rem; font-weight:700; }}
@keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.5}} }}
hr {{ border-color:{BORDER} !important; margin:14px 0 !important; }}
/* Streamlit tabs */
.stTabs [data-baseweb="tab-list"] {{ background:{BG_CARD2}; border-radius:10px; padding:4px; gap:4px; }}
.stTabs [data-baseweb="tab"] {{ border-radius:8px; padding:6px 20px;
    font-weight:600; font-size:.85rem; color:{TEXT_SEC}; }}
.stTabs [aria-selected="true"] {{ background:{BG_CARD}; color:{TEXT}; }}
</style>""", unsafe_allow_html=True)


# ── Data helpers ──────────────────────────────────────────────────────────────

@st.cache_resource
def _sb():
    url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL","")
    key = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY","")
    if not url or not key: return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception: return None

@st.cache_data(ttl=REFRESH_SEC)
def load_estado(par: str) -> dict:
    sb = _sb()
    if sb:
        try:
            r = sb.table("crypto_grid_state").select("estado").eq("par", par).single().execute()
            if r.data: return r.data["estado"]
        except Exception: pass
    p = BASE_DIR / ("estado_grid.json" if par == "BTC_USDT" else f"estado_grid_{par}.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

@st.cache_data(ttl=REFRESH_SEC)
def load_historico(par: str) -> list:
    sb = _sb()
    if sb:
        try:
            r = (sb.table("crypto_operaciones").select("tipo,precio,qty,pnl,timestamp")
                 .eq("par", par).order("timestamp", desc=False).limit(500).execute())
            return r.data or []
        except Exception: pass
    fname = "historico_operaciones.json" if par == "BTC_USDT" else f"historico_operaciones_{par}.json"
    p = BASE_DIR / "data" / fname
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

@st.cache_data(ttl=REFRESH_SEC)
def get_price(par: str) -> float:
    try:
        r = requests.get("https://api.crypto.com/exchange/v1/public/get-tickers",
                         params={"instrument_name": par}, timeout=10)
        return float(r.json()["result"]["data"][0].get("last") or 0)
    except Exception: return 0.0

@st.cache_data(ttl=120)
def get_candles(par: str, limit: int = 48) -> list:
    try:
        r = requests.get("https://api.crypto.com/exchange/v1/public/get-candlestick",
                         params={"instrument_name": par, "timeframe": "1h", "count": limit},
                         timeout=15)
        data = r.json()["result"]["data"]
        return sorted([{"ts": int(c.get("t") or 0)//1000,
                        "o": float(c.get("o") or 0), "h": float(c.get("h") or 0),
                        "l": float(c.get("l") or 0), "c": float(c.get("c") or 0)}
                       for c in data], key=lambda x: x["ts"])
    except Exception: return []


# ── Header ────────────────────────────────────────────────────────────────────
col_h1, col_h2 = st.columns([3,1])
with col_h1:
    st.markdown(f"""
    <h1 style="font-size:1.75rem;font-weight:800;color:#f59e0b;margin:0;letter-spacing:-.5px;">
      ₿ Crypto Bot — Grid Trading
    </h1>
    <p style="color:{TEXT_SEC};font-size:.83rem;margin:3px 0 0;">
      BTC · ETH · Estrategia Grid + Filtro EMA 200
    </p>""", unsafe_allow_html=True)
with col_h2:
    st.markdown(f"""
    <div style="text-align:right;padding-top:8px;">
      <span class="paper-badge" style="color:#f59e0b;">PAPER TRADING</span>&nbsp;
      <span class="live-badge">● LIVE</span>
    </div>""", unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)


# ── Render función por par ────────────────────────────────────────────────────

def render_par(par: str):
    coin      = par.split("_")[0]
    icon      = COIN_ICON[par]
    acc_color = COIN_COLOR[par]

    estado    = load_estado(par)
    historico = load_historico(par)
    precio    = get_price(par) or estado.get("precio_ultimo", 0)
    candles   = get_candles(par)

    if not estado:
        st.markdown(f"""
        <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:12px;
                    padding:40px;text-align:center;margin:20px 0;">
          <div style="font-size:3rem;">{icon}</div>
          <h3 style="color:{acc_color};">Sin datos para {par}</h3>
          <p style="color:{TEXT_SEC};">El bot no ha corrido aún para este par.</p>
        </div>""", unsafe_allow_html=True)
        return

    niveles      = estado.get("niveles", [])
    pnl_total    = estado.get("pnl_realizado_usdt", 0)
    capital      = estado.get("capital_usdt", 1000)
    grid_lower   = estado.get("grid_lower", 0)
    grid_upper   = estado.get("grid_upper", 0)
    open_niv     = [n for n in niveles if n["estado"] != "idle"]
    ultima_act   = estado.get("ultima_actualizacion", "")
    roi_pct      = (pnl_total / capital * 100) if capital else 0
    sells        = [t for t in historico if t["tipo"] == "SELL"]
    buys         = [t for t in historico if t["tipo"] == "BUY"]
    unrealized   = sum((precio - n["precio"]) * n.get("btc_qty", 0) for n in open_niv)
    dentro       = grid_lower <= precio <= grid_upper
    rango        = grid_upper - grid_lower
    precio_pct   = max(0, min(100, (precio - grid_lower) / rango * 100)) if rango else 50

    # ── KPIs ──────────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    def kpi(col, label, value, sub, color):
        col.markdown(f"""
        <div class="kpi-card" style="border-top:3px solid {color};">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value" style="color:{color};">{value}</div>
          <div class="kpi-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

    kpi(k1, f"{coin} Precio",    f"{icon} ${precio:,.2f}", "en tiempo real", acc_color)
    kpi(k2, "PnL Realizado",
        f"{'+'if pnl_total>=0 else ''}{pnl_total:.4f}",
        "USDT", GREEN if pnl_total>=0 else RED)
    kpi(k3, "ROI",
        f"{'+'if roi_pct>=0 else ''}{roi_pct:.2f}%",
        f"sobre ${capital:,.0f} capital", GREEN if roi_pct>=0 else RED)
    kpi(k4, "PnL No Real.",
        f"{'+'if unrealized>=0 else ''}{unrealized:.4f}",
        f"{len(open_niv)} posiciones", GREEN if unrealized>=0 else RED)
    kpi(k5, "Operaciones", str(len(historico)),
        f"{len(buys)} compras · {len(sells)} ventas", BLUE)
    kpi(k6, "Rango Grid",
        f"${grid_lower//1000 if grid_lower>=1000 else grid_lower}–${grid_upper//1000 if grid_upper>=1000 else grid_upper}{'K' if grid_upper>=1000 else ''}",
        "✓ Dentro" if dentro else "⚠ FUERA",
        GREEN if dentro else RED)

    # Barra posición
    st.markdown(f"""
    <div style="margin:14px 0 4px;">
      <div style="display:flex;justify-content:space-between;
                  font-size:.68rem;color:{TEXT_M};margin-bottom:3px;">
        <span>${grid_lower:,}</span>
        <span style="color:{acc_color};font-weight:600;">
          {icon} ${precio:,.2f} ({precio_pct:.0f}%)
        </span>
        <span>${grid_upper:,}</span>
      </div>
      <div style="background:{BORDER};border-radius:6px;height:7px;overflow:hidden;">
        <div style="width:{precio_pct}%;height:7px;border-radius:6px;
                    background:linear-gradient(90deg,{acc_color},{GREEN});"></div>
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Chart + Posiciones ────────────────────────────────────────────────────
    col_c, col_p = st.columns([3, 2])

    with col_c:
        st.markdown(f'<div class="sec-title">Precio {coin} vs Grid (últimas 48h)</div>',
                    unsafe_allow_html=True)
        fig = go.Figure()
        if candles:
            fig.add_trace(go.Candlestick(
                x=list(range(len(candles))),
                open=[c["o"] for c in candles], high=[c["h"] for c in candles],
                low= [c["l"] for c in candles], close=[c["c"] for c in candles],
                increasing_line_color=GREEN, decreasing_line_color=RED,
                increasing_fillcolor=GREEN, decreasing_fillcolor=RED, showlegend=False,
            ))
        xr = [0, max(len(candles)-1, 1)]
        for n in niveles:
            p = n["precio"]; is_open = n["estado"] == "buy_open"
            fig.add_shape(type="line", x0=xr[0], x1=xr[1], y0=p, y1=p,
                line=dict(color=RED if is_open else "#334155",
                          width=1.5 if is_open else 0.7,
                          dash="solid" if is_open else "dot"))
            if is_open:
                fig.add_annotation(x=xr[1], y=p, text=f" ${p:,.0f} ●",
                    showarrow=False, xanchor="left",
                    font=dict(color=RED, size=10, family="Inter"))
        fig.add_hline(y=precio, line=dict(color=acc_color, width=2),
            annotation_text=f"  ${precio:,.2f}",
            annotation_font=dict(color=acc_color, size=11),
            annotation_position="right")
        fig.add_hrect(y0=grid_lower, y1=grid_upper,
            fillcolor="rgba(99,102,241,0.04)", line_width=0)
        fig.update_layout(
            height=360, paper_bgcolor=BG_CARD, plot_bgcolor=BG_CARD,
            margin=dict(l=10, r=90, t=10, b=20),
            xaxis=dict(showgrid=False, showticklabels=False,
                       rangeslider=dict(visible=False), linecolor=BORDER),
            yaxis=dict(tickformat="$,.0f", tickfont=dict(color=TEXT_M, size=10),
                       gridcolor=BG_CARD2, linecolor=BORDER),
            font=dict(family="Inter, sans-serif"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        if ultima_act:
            try:
                dt = datetime.fromisoformat(ultima_act)
                st.markdown(f'<p style="font-size:.68rem;color:{TEXT_M};margin:-8px 0 0;">'
                            f'Actualizado: {dt.strftime("%Y-%m-%d %H:%M UTC")}</p>',
                            unsafe_allow_html=True)
            except Exception: pass

    with col_p:
        st.markdown(f'<div class="sec-title">Posiciones Abiertas ({len(open_niv)})</div>',
                    unsafe_allow_html=True)
        if open_niv:
            for n in sorted(open_niv, key=lambda x: x["precio"], reverse=True):
                pnl_n = (precio - n["precio"]) * n.get("btc_qty", 0)
                pc    = GREEN if pnl_n >= 0 else RED
                qty_key = "btc_qty"
                st.markdown(f"""
                <div style="background:{BG_CARD2};border:1px solid {BORDER};
                            border-left:3px solid {RED};border-radius:8px;
                            padding:9px 13px;margin-bottom:7px;
                            display:flex;justify-content:space-between;align-items:center;">
                  <div>
                    <div style="font-weight:700;color:{TEXT};font-size:.88rem;">${n['precio']:,.2f}</div>
                    <div style="font-size:.68rem;color:{TEXT_M};">{n.get(qty_key,0):.6f} {coin}</div>
                  </div>
                  <div style="text-align:right;">
                    <div style="font-weight:700;color:{pc};font-size:.88rem;">
                      {'+'if pnl_n>=0 else ''}{pnl_n:.4f} USDT
                    </div>
                    <div style="font-size:.68rem;color:{TEXT_M};">no realizado</div>
                  </div>
                </div>""", unsafe_allow_html=True)
            uc = GREEN if unrealized>=0 else RED
            st.markdown(f"""
            <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;
                        padding:9px 13px;text-align:center;">
              <span style="font-size:.68rem;color:{TEXT_M};">TOTAL&nbsp;&nbsp;</span>
              <span style="font-weight:800;color:{uc};">
                {'+'if unrealized>=0 else ''}{unrealized:.4f} USDT
              </span>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:{BG_CARD2};border:1px solid {BORDER};border-radius:8px;
                        padding:24px;text-align:center;color:{TEXT_M};">Sin posiciones abiertas</div>
            """, unsafe_allow_html=True)

        st.markdown(f'<div class="sec-title" style="margin-top:18px;">Configuración</div>',
                    unsafe_allow_html=True)
        step = estado.get("nivel_step", 0)
        for label, val in [
            ("Par", estado.get("par","—")),
            ("Capital", f"${capital:,.0f} USDT"),
            ("Niveles", f"{estado.get('grid_levels','—')} (step ${step:,.0f})"),
            ("Cap/nivel", f"${estado.get('capital_por_nivel',0):.2f} USDT"),
            ("Rango", f"${grid_lower:,} – ${grid_upper:,}"),
        ]:
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;padding:4px 0;
                        border-bottom:1px solid {BG_CARD2};">
              <span style="font-size:.76rem;color:{TEXT_M};">{label}</span>
              <span style="font-size:.76rem;font-weight:600;color:{TEXT};">{val}</span>
            </div>""", unsafe_allow_html=True)

    # ── Historial ─────────────────────────────────────────────────────────────
    st.markdown(f'<div class="sec-title">Historial de Operaciones</div>', unsafe_allow_html=True)
    if historico:
        rows = ""
        for t in list(reversed(historico))[:50]:
            badge = f'<span class="badge-{"buy" if t["tipo"]=="BUY" else "sell"}">{t["tipo"]}</span>'
            pr    = float(t.get("precio",0))
            qty   = float(t.get("qty",0))
            pnl_v = t.get("pnl")
            pnl_s = f'<span style="color:{GREEN};">+{float(pnl_v):.4f}</span>' if pnl_v else "—"
            try:
                ts = datetime.fromisoformat(str(t.get("timestamp",""))).strftime("%d/%m %H:%M")
            except Exception: ts = str(t.get("timestamp",""))[:16]
            rows += f"""<tr style="border-bottom:1px solid {BORDER};">
              <td style="padding:7px 12px;color:{TEXT_M};font-size:.76rem;">{ts}</td>
              <td style="padding:7px 12px;">{badge}</td>
              <td style="padding:7px 12px;font-weight:600;color:{TEXT};">${pr:,.2f}</td>
              <td style="padding:7px 12px;color:{TEXT_SEC};font-size:.78rem;">{qty:.6f}</td>
              <td style="padding:7px 12px;font-size:.78rem;">{pnl_s}</td>
            </tr>"""
        st.markdown(f"""
        <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:10px;overflow:hidden;">
          <table style="width:100%;border-collapse:collapse;">
            <thead><tr style="background:{BG_CARD2};">
              {''.join(f'<th style="padding:9px 12px;text-align:left;font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;color:{TEXT_M};">{h}</th>' for h in ["Fecha UTC","Tipo","Precio","Qty","PnL (USDT)"])}
            </tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>""", unsafe_allow_html=True)
        if len(historico) > 50:
            st.markdown(f'<p style="font-size:.68rem;color:{TEXT_M};margin-top:5px;">'
                        f'Últimas 50 de {len(historico)}</p>', unsafe_allow_html=True)
    else:
        st.markdown(f"""<div style="background:{BG_CARD};border:1px solid {BORDER};
                        border-radius:10px;padding:28px;text-align:center;color:{TEXT_M};">
                        Sin operaciones aún.</div>""", unsafe_allow_html=True)


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_btc, tab_eth = st.tabs(["₿  BTC / USDT", "Ξ  ETH / USDT"])

with tab_btc:
    render_par("BTC_USDT")

with tab_eth:
    render_par("ETH_USDT")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(f"""
<div style="display:flex;justify-content:space-between;">
  <span style="font-size:.68rem;color:{TEXT_M};">
    Auto-refresh {REFRESH_SEC}s · Crypto.com API + Supabase
  </span>
  <span style="font-size:.68rem;color:{TEXT_M};">Socrates Labs · {datetime.now().year}</span>
</div>
<meta http-equiv='refresh' content='{REFRESH_SEC}'>
""", unsafe_allow_html=True)
