import streamlit as st

from services.runtime import execute
from core.publication import restore
import json


def render_recovery(mode, default=None):
    from services.runtime import get_repository
    names, revision = get_repository(mode).recovery_options()
    if not names:
        return
    with st.expander("Eliminar o reiniciar competencia"):
        st.caption("Funciona aunque una hoja contenga entradas inválidas. Eliminar retira solo esa competencia de las hojas visibles y guarda una copia completa en Papelera; las demás competencias se conservan.")
        with st.form("force_recovery"):
            name = st.selectbox("Competencia que se modificará", names, index=names.index(default) if default in names else 0)
            action = st.selectbox("Acción", ["Reiniciar resultados", "Reiniciar fase actual", "Reiniciar eliminatorias", "Reiniciar competencia", "Eliminar"])
            st.caption("Reiniciar resultados conserva equipos y grupos, pero borra clasificaciones, tiempos y podio. Reiniciar competencia también retira los equipos.")
            exact = st.text_input("Nombre exacto de la competencia")
            confirm = st.checkbox("Confirmo la acción y el respaldo de los datos anteriores")
            if st.form_submit_button("Aplicar acción", type="primary"):
                if not confirm or exact != name:
                    st.error("Confirma la acción y escribe el nombre exacto del torneo.")
                else:
                    execute(mode, revision, None, "Acción completada. Se guardó el respaldo anterior.", recovery=(name, action))


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
