import pandas as pd
import streamlit as st
from core.sheet_flow import active_participants, history_rows
from utils.helpers import csv_seguro


def actuales(c):
    st.header("Participantes actuales")
    rows = active_participants(c)
    st.metric("Equipos en competencia", len(rows))
    st.caption("Fase: " + c.config.fase_actual)
    st.dataframe(pd.DataFrame(rows, columns=["Equipo", "Grupo de origen", "Fase actual"]), hide_index=True, width="stretch")


def historial(c):
    st.header("Historial")
    if c.config.sistema == "Tiempos":
        from components.tiempos import history
        history(c)
        return
    rows = history_rows(c)
    phases = list(dict.fromkeys(r['Fase'] for r in rows))
    phase = st.selectbox("Fase del historial", ["Todas"] + phases)
    frame = pd.DataFrame([r for r in rows if phase == "Todas" or r['Fase'] == phase],
                         columns=["Fase", "Partido", "Equipo", "Grupo", "Resultado"])
    st.dataframe(frame, hide_index=True, width="stretch")
    st.download_button("Descargar historial CSV", csv_seguro(frame), "historial.csv", "text/csv")
