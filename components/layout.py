from html import escape
import streamlit as st

from core.eliminatorias import ORDEN_FASES, partidos_fase

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stApp {font-family:'DM Sans',sans-serif;}
.stApp {background:#F3F7F6;color:#173B3D;}
h1,h2,h3 {font-family:'Space Grotesk',sans-serif!important;letter-spacing:-.04em!important;}
[data-testid="stSidebar"] {background:#0D9648;}
[data-testid="stSidebar"] * {color:#e6efee;}
[data-testid="stSidebar"] input {color:#173B3D!important;}
[data-testid="stSidebar"] [data-baseweb="select"] * {color:#173B3D;}
[data-testid="stSidebar"] .stButton button {background:#0087C3;color:white;border:1px solid #FFFFFF;}
.block-container {max-width:1920px;padding-top:2.5rem;padding-bottom:3rem;}
.brand {font-family:'Space Grotesk',sans-serif;font-size:25px;font-weight:700;letter-spacing:-1px;}
.brand span {color:#9FCF67;}
.eyebrow {color:#647c81;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:12px;}
.hero {border-radius:18px;background:linear-gradient(110deg,#0D9648,#00A99D,#0087C3);color:#f9fffc;padding:30px 34px;margin:18px 0 26px;position:relative;overflow:hidden;}
.hero h1 {color:#f9fffc!important;margin:8px 0 5px;font-size:38px;line-height:1.1;}
.hero p {color:#FFFFFF;margin-bottom:0;font-size:14px;}
.hero .tag {display:inline-block;border:1px solid #476b6b;border-radius:30px;padding:5px 10px;font-size:10px;letter-spacing:1px;}
.hero .accent {position:absolute;right:32px;top:18px;color:#9FCF67;font-size:86px;opacity:.6;font-family:monospace;}
[data-testid="stMetric"] {background:white;border:1px solid #e0e8e7;border-radius:12px;padding:16px 20px;}
[data-testid="stMetricLabel"] {font-size:12px;color:#62787d;}
[data-testid="stMetricValue"] {font-family:'Space Grotesk',sans-serif;font-size:28px!important;}
.group-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;margin-top:16px;}
.group-card {background:white;border:1px solid #dde5e5;border-radius:14px;overflow:hidden;}
.group-head {border-left:4px solid #0D9648;padding:17px 20px;border-bottom:1px solid #e8eeed;font-weight:700;display:flex;justify-content:space-between;align-items:center;}
.group-count {color:#75898b;font-size:11px;font-weight:500;}
.team-row {display:flex;align-items:center;justify-content:space-between;padding:12px 20px;border-bottom:1px solid #f0f3f3;font-size:13px;}
.team-row:last-child {border:0;}
.metrics-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px;margin:20px 0 12px;}
.metric-card {background:white;border:1px solid #e0e8e7;border-radius:12px;padding:16px 18px;}
.metric-label {font-size:12px;color:#62787d;margin-bottom:5px;}
.metric-value {font-family:'Space Grotesk',sans-serif;font-size:28px;white-space:nowrap;}
.badge {font-size:10px;padding:4px 7px;border-radius:5px;background:#f0f4f4;color:#718184;white-space:nowrap;}
.badge.ok {background:#e1f7ee;color:#0D9648;}.badge.out {background:#fff0ed;color:#ab5149;}
.section-label {font-size:11px;font-weight:700;letter-spacing:1.6px;color:#78908e;margin-top:26px;}
.bracket {display:flex;gap:24px;overflow-x:auto;padding:12px 2px 25px;align-items:stretch;}
.round {min-width:245px;display:flex;flex-direction:column;}
.round-title {font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#547577;margin-bottom:16px;}
.round-body {display:flex;flex-direction:column;justify-content:space-around;gap:16px;flex:1;}
.match-card {background:white;border:1px solid #dce6e4;border-radius:10px;overflow:hidden;}
.match-label {background:#eef3f2;padding:7px 12px;font-size:10px;color:#748888;}
.match-team {padding:10px 12px;border-bottom:1px solid #edf2f1;font-size:12px;display:flex;justify-content:space-between;}
.match-team.winner {color:#0D9648;background:#ecfbf4;font-weight:700;}
.champion {background:#e2f6ea;border:1px solid #b1d8be;border-radius:18px;padding:32px;text-align:center;margin:20px 0;}
.champion h2 {color:#175b3c!important;font-size:36px;}
.muted {color:#72868a;font-size:13px;}
@media(max-width:700px){.hero{padding:22px}.hero h1{font-size:28px}.hero .accent{display:none}.block-container{padding:1.5rem 1rem}.group-grid{grid-template-columns:1fr}}
</style>
"""


def inject_style():
    st.markdown(CSS, unsafe_allow_html=True)


def hero(c):
    st.markdown(f'<div class="hero"><span class="tag">TORNEOS DE ROBÓTICA</span>'
                f'<h1>{escape(c.config.competencia)}</h1><p>{escape(c.config.titulo)} · {escape(c.config.fase_actual)}</p>'
                f'<div class="accent">⌘</div></div>', unsafe_allow_html=True)


def metrics(c):
    values = [("Equipos", f"{len(c.teams)} / {c.config.numero_equipos}"),
              ("Participantes", c.config.numero_participantes),
              ("Grupos", c.config.numero_grupos if c.config.torneo_iniciado else 0),
              ("Clasificados", f"{sum(t.clasificado for t in c.teams)} / {c.config.cupos_clasificados}"),
              ("Partidos finalizados", f"{sum(bool(m.ganador) for m in c.matches)} / {len(c.matches)}")]
    st.markdown('<div class="metrics-grid">' + ''.join(
        f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>'
        for label, value in values) + '</div>', unsafe_allow_html=True)


def group_cards(c):
    from core.grupos import nombre_columna
    if not c.config.torneo_iniciado:
        st.info("Los grupos se mostrarán cuando el administrador los genere.")
        return
    cards = []
    for i in range(c.config.numero_grupos):
        group = nombre_columna(i + 1)
        teams = [t for t in c.teams if t.grupo == group]
        rows = ""
        for t in teams:
            style = "ok" if t.clasificado else "out" if t.estado == "Eliminado" else ""
            rows += f'<div class="team-row"><span>{escape(t.nombre_equipo)}</span><span class="badge {style}">{escape({'Clasificado': 'Clasifica', 'Eliminado': 'No clasifica'}.get(t.estado, t.estado))}</span></div>'
        cards.append(f'<div class="group-card"><div class="group-head">Equipo {i+1}<span class="group-count">{len(teams):02d}</span></div>{rows}</div>')
    st.markdown('<div class="group-grid">' + "".join(cards) + '</div>', unsafe_allow_html=True)


def champion(c):
    if c.config.campeon:
        st.markdown(f'<div class="champion"><div>🏆 CAMPEÓN · TORNEO STEM 2026</div><h2>{escape(c.name(c.config.campeon))}</h2>'
                    f'<span>{escape(c.config.competencia)}</span></div>', unsafe_allow_html=True)


def bracket(c):
    if not c.matches:
        st.info("El cuadro estará disponible al generar las eliminatorias.")
        return
    first = min(ORDEN_FASES.index(m.fase) for m in c.matches)
    html = '<div class="bracket">'
    for phase in ORDEN_FASES[first:]:
        matches = partidos_fase(c, phase)
        html += f'<div class="round"><div class="round-title">{phase} →</div><div class="round-body">'
        if not matches:
            html += '<div class="match-card"><div class="match-team">Esperando la ronda anterior</div></div>'
        for m in matches:
            html += f'<div class="match-card"><div class="match-label">PARTIDO {m.numero_partido} · {m.estado.upper()}</div>'
            for team_id in (m.equipo_1, m.equipo_2):
                win = bool(team_id and team_id == m.ganador)
                html += f'<div class="match-team {"winner" if win else ""}"><span>{escape(c.name(team_id))}</span><span>{"✓" if win else ""}</span></div>'
            html += '</div>'
        html += '</div></div>'
    st.markdown(html + '</div>', unsafe_allow_html=True)
    champion(c)
