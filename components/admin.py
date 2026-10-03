import streamlit as st

from core.tournament import reiniciar
from services.runtime import execute
from core.publication import archive, restore
import json


def render_recovery(mode, default=None):
    from services.runtime import get_repository
    names, revision = get_repository(mode).recovery_options()
    if not names:
        return
    with st.expander("Recuperación forzada"):
        st.caption("Funciona aunque una hoja contenga entradas inválidas. Guarda un respaldo antes de retirar el torneo o reiniciarlo; conserva las otras competencias.")
        with st.form("force_recovery"):
            name = st.selectbox("Torneo a recuperar", names, index=names.index(default) if default in names else 0)
            action = st.selectbox("Acción forzada", ["Eliminar", "Reiniciar resultados", "Reiniciar competencia"])
            st.caption("Reiniciar resultados conserva equipos y grupos, pero borra clasificaciones, tiempos y podio. Reiniciar competencia también retira los equipos.")
            exact = st.text_input("Nombre exacto para recuperación forzada")
            confirm = st.checkbox("Confirmo la recuperación forzada y el respaldo de los datos anteriores")
            if st.form_submit_button("Ejecutar recuperación", type="primary"):
                if not confirm or exact != name:
                    st.error("Confirma la acción y escribe el nombre exacto del torneo.")
                else:
                    execute(mode, revision, None, "Recuperación completada. Se guardó el respaldo anterior.", recovery=(name, action))


def render(state, c, mode, revision, admin):
    st.header("Administración")
    if not admin:
        st.info("Accede como administrador desde el menú lateral.")
        return
    render_recovery(mode, c.config.competencia if c else None)
    if state.recovery_backups:
        with st.expander("Respaldos de recuperación"):
            key = st.selectbox("Respaldo", list(state.recovery_backups), format_func=lambda k: state.recovery_backups[k]["competencia"] + " · " + state.recovery_backups[k]["accion"] + " · " + k[:6])
            st.download_button("Descargar respaldo de recuperación", json.dumps(state.recovery_backups[key], ensure_ascii=False, indent=2), "respaldo-torneo.json", "application/json")
    with st.expander("Papelera", expanded=not c):
        if state.archived:
            archive_id = st.selectbox("Competencia eliminada", list(state.archived),
                                      format_func=lambda key: state.archived[key].config.competencia + " · " + key[:6])
            if st.button("Restaurar competencia"):
                execute(mode, revision, lambda s: restore(s, archive_id), "Competencia restaurada con sus equipos y resultados.")
        else:
            st.caption("La papelera está vacía.")
    if not c:
        return
    st.write(f"Competencia seleccionada: **{c.config.competencia}**")
    with st.expander("Eliminar competencia"):
        st.caption("Se retira de la aplicación y de las hojas del torneo. Sus equipos y resultados se guardan en la papelera para poder restaurarlos.")
        with st.form("delete_competition"):
            exact = st.text_input("Nombre de la competencia que vas a eliminar")
            if st.form_submit_button("Eliminar competencia"):
                if exact != c.config.competencia:
                    st.error("Escribe el nombre exacto de la competencia seleccionada.")
                else:
                    execute(mode, revision, lambda s: archive(s, c.config.competencia), "Competencia eliminada. Puedes recuperarla desde Papelera.")
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
