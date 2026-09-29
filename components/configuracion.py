import streamlit as st

from core.models import Config
from core.grupos import distribuir, nombre_columna
from core.tournament import configurar, crear_competencia, iniciar_grupos
from services.runtime import execute


def render(state, c, mode, revision, admin):
    st.header("Configurar torneo")
    st.caption("Define los equipos, los grupos y los cupos de cada competencia.")
    if not admin:
        if c:
            st.json({"competencia": c.config.competencia, "numero_equipos": c.config.numero_equipos,
                     "numero_grupos": c.config.numero_grupos, "numero_participantes": c.config.numero_participantes,
                     "cupos_clasificados": c.config.cupos_clasificados, "fase_actual": c.config.fase_actual})
        st.info("El administrador puede crear y configurar competencias.")
        return
    with st.expander("＋ Crear una competencia", expanded=not state.competitions):
        with st.form("new_competition"):
            name = st.text_input("Nombre de la competencia", placeholder="Seguidor de línea")
            left, right = st.columns(2)
            total = left.number_input("Cantidad total de equipos", min_value=2, max_value=4096, value=32)
            groups = right.number_input("Cantidad de grupos", min_value=1, max_value=4096, value=6)
            participants = left.number_input("Cantidad total de participantes", min_value=0, value=0)
            qualified = right.selectbox("Equipos que avanzan", [2, 4, 8, 16, 32, 64], index=3)
            if st.form_submit_button("Crear competencia", type="primary"):
                execute(mode, revision, lambda s: crear_competencia(s, Config(name, total, groups, participants, qualified)), "Competencia creada.")
    if not c:
        return
    cfg = c.config
    st.subheader(cfg.competencia)
    if cfg.torneo_iniciado:
        st.success(f"Grupos guardados · {cfg.metodo_grupos} · Fase: {cfg.fase_actual}")
        st.write("Distribución: " + cfg.equipos_por_grupo)
        st.caption("Para cambiar grupos o cupos: Administración → reiniciar eliminatorias si existen → reiniciar fase de grupos.")
        with st.form("participants_total"):
            value = st.number_input("Total esperado de participantes", min_value=0, value=cfg.numero_participantes)
            if st.form_submit_button("Actualizar total de participantes"):
                execute(mode, revision, lambda s: setattr(s.competitions[cfg.competencia].config, "numero_participantes", value))
        return
    with st.form("configure_groups"):
        a, b = st.columns(2)
        total = a.number_input("Total de equipos esperado", 2, 4096, cfg.numero_equipos)
        groups = b.number_input("Total de grupos", 1, 4096, cfg.numero_grupos)
        participants = a.number_input("Participantes esperados", min_value=0, value=cfg.numero_participantes)
        qualified = b.selectbox("Cupos de clasificación", [2, 4, 8, 16, 32, 64], index=[2, 4, 8, 16, 32, 64].index(cfg.cupos_clasificados))
        method = st.radio("Método de distribución", ["Orden original", "Sorteo aleatorio"], horizontal=True)
        generic = st.checkbox("Completar equipos faltantes con nombres genéricos")
        save = st.form_submit_button("Guardar configuración")
        generate = st.form_submit_button("GENERAR GRUPOS", type="primary")
        if save or generate:
            def operation(s):
                current = s.competitions[cfg.competencia]
                configurar(current, total, groups, participants, qualified)
                if generate:
                    iniciar_grupos(current, method == "Sorteo aleatorio", generic)
            execute(mode, revision, operation, "Grupos generados y guardados." if generate else "Configuración guardada.")
    counts = distribuir(cfg.numero_equipos, cfg.numero_grupos)
    st.caption("Distribución guardada en la configuración: " + " · ".join(f"{nombre_columna(i+1)}: {n}" for i, n in enumerate(counts)))
