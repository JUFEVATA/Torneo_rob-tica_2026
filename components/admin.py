import streamlit as st

from core.tournament import reiniciar
from services.runtime import execute


def render(c, mode, revision, admin):
    st.header("Administración")
    if not admin:
        st.info("Accede como administrador desde el menú lateral.")
        return
    st.write(f"Competencia seleccionada: **{c.config.competencia}**")
    st.caption("Cada reinicio afecta únicamente a esta competencia.")
    with st.form("reset"):
        scope = st.selectbox("Qué quieres reiniciar", ["Fase actual", "Eliminatorias", "Competencia completa"])
        st.warning("Fase actual: borra sus ganadores y rondas posteriores; en grupos también borra la asignación. Eliminatorias: conserva grupos y clasificados. Competencia completa: elimina equipos, grupos, partidos y campeón; conserva la configuración.")
        name = st.text_input("Escribe el nombre exacto de la competencia para confirmar")
        confirm = st.checkbox("Entiendo que esta acción elimina los datos indicados")
        if st.form_submit_button("Confirmar reinicio"):
            if not confirm or name != c.config.competencia:
                st.error("Confirma la acción y escribe el nombre exacto de la competencia.")
            else:
                execute(mode, revision, lambda s: reiniciar(s.competitions[c.config.competencia], scope, True), "Reinicio guardado.")
    st.divider()
    st.caption("Persistencia: Google Sheets en producción; archivo .demo/torneo.json en demostración. Las contraseñas se leen exclusivamente desde st.secrets.")
