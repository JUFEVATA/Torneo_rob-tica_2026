from html import escape
from base64 import b64encode
import pandas as pd
import streamlit as st
from components.layout import group_cards, bracket
from core.publication import shown_stage, LABELS, podium
from core.sheet_flow import TO_PUBLIC
from core.tree import round_entries, tree_phases, tree_svg


def home(c):
    phase = shown_stage(c)
    st.markdown(f'<div class="hero"><span class="tag">{escape(c.config.titulo)}</span><h1>{escape(c.config.competencia)}</h1><p>Etapa actual · {escape(LABELS[phase])}</p></div>', unsafe_allow_html=True)
    st.header(LABELS[phase])
    if phase == "Grupos":
        group_cards(c)
    elif phase == "Inscripción":
        st.info(f"{len(c.teams)} equipos inscritos. La competencia todavía no ha iniciado.")
    elif phase == "Finalizado":
        render_podium(c)
    else:
        entries = round_entries(c, phase)
        st.caption(f"{len(entries)} equipos en esta etapa")
        if not entries:
            st.info("Los participantes aparecerán al clasificar desde la etapa anterior.")
        else:
            st.dataframe(pd.DataFrame([{"Equipo": c.name(tid), "Estado": TO_PUBLIC[status]} for tid, status in entries]), hide_index=True, width="stretch")


def render_tree(c):
    st.header("Ruta al campeonato")
    phases = tree_phases(c)
    stage = shown_stage(c)
    context_index = max(0, len(phases)-3)
    default = phases[min(phases.index(stage), context_index)] if stage in phases else phases[context_index] if stage == "Finalizado" else phases[0]
    start = st.selectbox("Ver árbol desde", phases, index=phases.index(default), format_func=lambda f: LABELS[f])
    if c.config.sistema == "Libre":
        st.caption("Clasificación libre. Las líneas muestran el avance entre etapas.")
        detail = st.checkbox("Ampliar nombres")
        svg = tree_svg(c, start)
        if detail:
            st.caption("Desliza horizontalmente para recorrer el árbol ampliado.")
        if not detail:
            st.image(svg, width="stretch")
        else:
            data = b64encode(svg.encode()).decode()
            st.html('<div style="overflow-x:auto;background:#fff;border:1px solid #dce6e4;border-radius:16px;padding:12px"><img alt="Árbol del torneo" style="display:block;width:1500px;max-width:none" src="data:image/svg+xml;base64,' + data + '"></div>')
    else:
        bracket(c)


def render_podium(c):
    st.header("Podio")
    result = podium(c)
    names = {position: escape(c.name(tid)) if tid else "Por definir" for position, tid in result.items()}
    st.markdown('<div class="podium-grid">' + ''.join(
        f'<div class="podium-place place-{position}"><div class="podium-medal">{medal}</div><div class="podium-position">{position}.º puesto</div><h3>{names[position]}</h3></div>'
        for position, medal in [(2, "🥈"), (1, "🥇"), (3, "🥉")]) + '</div>', unsafe_allow_html=True)
