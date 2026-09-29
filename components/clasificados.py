import pandas as pd
import streamlit as st

from core.eliminatorias import ORDEN_FASES, fase_para, partidos_fase
from core.tournament import iniciar_eliminatorias
from services.runtime import execute
from services.serialization import clasificados_actuales


def render(c, mode, revision, admin):
    st.header("Clasificados")
    original = [t for t in c.teams if t.clasificado]
    st.subheader(f"Clasificados a {fase_para(c.config.cupos_clasificados)}")
    st.write(f"Clasificados de grupos: **{len(original)} / {c.config.cupos_clasificados}**")
    st.progress(min(len(original) / c.config.cupos_clasificados, 1.0))
    if original:
        st.dataframe(pd.DataFrame([{"Equipo": t.nombre_equipo, "Grupo": t.grupo} for t in original]), hide_index=True, width="stretch")
    if c.matches:
        phase, ids = clasificados_actuales(c)
        st.subheader(f"Clasificados a {phase}" if phase != "Campeón" else "🏆 Campeón")
        if ids:
            for i, team_id in enumerate(ids, 1):
                st.write(f"{i}. {c.name(team_id)}")
        else:
            st.caption("Los ganadores de la fase actual aparecerán aquí.")
        if phase != "Campeón":
            winners = [m.ganador for m in partidos_fase(c, phase) if m.ganador]
            index = ORDEN_FASES.index(phase)
            next_phase = ORDEN_FASES[index + 1] if phase != "Final" else "Campeón"
            st.caption(f"Avanzan a {next_phase}: {len(winners)} / {len(ids) // 2}")
            for team_id in winners:
                st.write(f"✓ {c.name(team_id)}")
        st.info(f"Fase actual: {c.config.fase_actual}. Los cruces están disponibles en Eliminatorias.")
    elif admin:
        method = st.radio("Emparejamiento inicial", ["Orden de inscripción", "Sorteo aleatorio"], horizontal=True)
        if st.button("GENERAR ELIMINATORIAS", type="primary", disabled=len(original) != c.config.cupos_clasificados or not c.config.torneo_iniciado):
            execute(mode, revision, lambda s: iniciar_eliminatorias(s.competitions[c.config.competencia], method == "Sorteo aleatorio"), "Eliminatorias guardadas.")
        st.caption("Se emparejan consecutivamente: 1 vs 2, 3 vs 4… La siguiente ronda se genera al terminar todos sus partidos.")
