from dataclasses import asdict
import pandas as pd
import streamlit as st

from core.models import ValidationError
from core.tournament import agregar_equipos, completar_genericos, editar_equipo, eliminar_equipo
from services.runtime import execute
from utils.helpers import csv_seguro, importar_csv


def render(c, mode, revision, admin):
    st.header("Equipos")
    registered = sum(t.numero_participantes for t in c.teams)
    st.caption(f"{len(c.teams)} / {c.config.numero_equipos} equipos · Participantes registrados: {registered} / {c.config.numero_participantes} total esperado")
    if registered > c.config.numero_participantes:
        st.info("Los participantes registrados superan el total esperado. Puedes actualizarlo en Configuración.")
    frame = pd.DataFrame([asdict(t) for t in c.teams])
    if not frame.empty:
        st.dataframe(frame.drop(columns=["competencia", "id_equipo"]), hide_index=True, width="stretch")
        st.download_button("Descargar equipos CSV", csv_seguro(frame), "equipos.csv", "text/csv")
    if not admin:
        return
    if not c.config.torneo_iniciado:
        tab1, tab2, tab3 = st.tabs(["Agregar equipo", "Pegar lista", "Importar CSV"])
        with tab1, st.form("add_team", clear_on_submit=True):
            name = st.text_input("Nombre del equipo")
            participants = st.number_input("Participantes del equipo", min_value=0, value=0)
            if st.form_submit_button("Agregar", type="primary"):
                execute(mode, revision, lambda s: agregar_equipos(s.competitions[c.config.competencia], [name], [participants]))
        with tab2, st.form("paste_teams", clear_on_submit=True):
            text = st.text_area("Un nombre por línea", height=160)
            if st.form_submit_button("Agregar lista"):
                names = [n.strip() for n in text.splitlines() if n.strip()]
                execute(mode, revision, lambda s: agregar_equipos(s.competitions[c.config.competencia], names))
        with tab3:
            st.caption("UTF-8, encabezado nombre_equipo; opcional: numero_participantes. Importación completa o sin cambios.")
            st.download_button("Descargar plantilla CSV", b"nombre_equipo,numero_participantes\nSwampy,3\nHercules,2\n", "plantilla_equipos.csv")
            upload = st.file_uploader("Seleccionar lista", type=["csv"])
            if upload and st.button("Importar equipos"):
                try:
                    names, participants = importar_csv(upload.getvalue())
                    execute(mode, revision, lambda s: agregar_equipos(s.competitions[c.config.competencia], names, participants))
                except ValidationError as error:
                    st.error(str(error))
        if st.button("Completar con Equipo 1, Equipo 2…", disabled=len(c.teams) >= c.config.numero_equipos):
            execute(mode, revision, lambda s: completar_genericos(s.competitions[c.config.competencia]))
    else:
        st.info("Los grupos están guardados. Puedes editar nombres e integrantes; para agregar o eliminar equipos, reinicia los grupos.")
    if c.teams:
        st.subheader("Editar un equipo")
        selected = st.selectbox("Equipo", [t.id_equipo for t in c.teams], format_func=c.name)
        team = next(t for t in c.teams if t.id_equipo == selected)
        with st.form(f"edit_{selected}"):
            name = st.text_input("Nombre", value=team.nombre_equipo)
            participants = st.number_input("Integrantes registrados", min_value=0, value=team.numero_participantes)
            if st.form_submit_button("Guardar equipo"):
                execute(mode, revision, lambda s: editar_equipo(s.competitions[c.config.competencia], selected, name, participants))
        if not c.config.torneo_iniciado:
            with st.expander("Eliminar equipo"):
                confirm = st.checkbox(f"Confirmo eliminar a {team.nombre_equipo}", key=f"delete_confirm_{selected}")
                if st.button("Eliminar equipo seleccionado", disabled=not confirm):
                    execute(mode, revision, lambda s: eliminar_equipo(s.competitions[c.config.competencia], selected))
