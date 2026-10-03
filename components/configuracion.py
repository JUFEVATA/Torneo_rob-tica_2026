import streamlit as st

from core.models import Config
from core.grupos import distribuir, nombre_columna
from core.tournament import configurar, crear_competencia, iniciar_grupos
from services.runtime import execute


def render(state, c, mode, revision, admin):
    if not admin:
        return
    st.header("Configurar torneo")
    with st.expander("Importar lista de grupos"):
        with st.form("import_groups"):
            text = st.text_area("Lista completa", height=250, placeholder="TORNEOS DE ROBÓTICA\nEquipo STEM 2026\nCompetencia: Sumo\nParticipantes: 85 | Grupos: 4\nEquipo 1\n• Nombre del equipo")
            if st.form_submit_button("Importar grupos"):
                from core.sheet_flow import parse_rosters, import_roster
                from core.models import ValidationError
                def operation(s):
                    rosters = parse_rosters([[text]])
                    if not rosters:
                        raise ValidationError("Pega el listado con su encabezado Competencia:.")
                    for roster in rosters:
                        import_roster(s, roster)
                execute(mode, revision, operation, "Lista importada con su distribución original.")
    with st.expander("＋ Crear una competencia", expanded=not state.competitions):
        with st.form("new_competition"):
            name = st.text_input("Nombre de la competencia", placeholder="Seguidor de línea")
            kind = st.selectbox("Tipo de competencia", ["Clasificación libre", "Seguidor de línea por tiempos"])
            left, right = st.columns(2)
            total = left.number_input("Cantidad total de equipos", min_value=2, max_value=4096, value=32)
            groups = right.number_input("Cantidad de grupos", min_value=1, max_value=4096, value=6)
            participants = left.number_input("Cantidad total de participantes", min_value=0, value=0)
            qualified = right.selectbox("Equipos que avanzan", [2, 4, 8, 16, 32, 64], index=3)
            if st.form_submit_button("Crear competencia", type="primary"):
                system = "Tiempos" if kind == "Seguidor de línea por tiempos" else "Libre"
                cap = min(16, max(n for n in (2, 4, 8, 16, 32, 64) if n <= total)) if system == "Tiempos" else qualified
                execute(mode, revision, lambda s: crear_competencia(s, Config(name, total, groups, participants, cap, sistema=system)), "Competencia creada.")
    if not c:
        return
    cfg = c.config
    st.subheader(cfg.competencia)
    if cfg.sistema == "Tiempos":
        st.info("Seguidor de línea: cuatro fases. Avanzan 16 → 8 → 4; la final define los tres puestos por el menor tiempo válido. Tres intentos y tres fallos nuevos por fase.")
    if cfg.torneo_iniciado:
        if not c.matches and all(t.estado == 'Pendiente' for t in c.teams):
            with st.expander("Cantidad de equipos y grupos", expanded=True):
                with st.form("resize_board"):
                    total = st.number_input("Equipos inscritos en competencia", 2, 4096, len(c.teams))
                    groups = st.number_input("Cantidad de bloques / grupos", 1, 4096, cfg.numero_grupos)
                    cupos = st.selectbox("Clasificados que avanzan", [2,4,8,16,32,64], index=[2,4,8,16,32,64].index(cfg.cupos_clasificados), disabled=cfg.sistema == "Tiempos")
                    method = st.selectbox("Distribuir equipos", ["Orden original", "Sorteo aleatorio"])
                    st.caption(f"{len(c.reserve)} equipos en reserva. Al reducir el total, se conservan los nombres sobrantes; al aumentarlo, se recuperan primero.")
                    if st.form_submit_button("Aplicar distribución"):
                        from core.group_board import resize_groups
                        execute(mode, revision, lambda s: resize_groups(s.competitions[cfg.competencia], total, groups, cupos, method == "Sorteo aleatorio"), "Distribución actualizada.")
        else:
            with st.form("regroup_active"):
                groups = st.number_input("Cantidad de bloques / grupos", 1, len(c.teams), cfg.numero_grupos)
                if st.form_submit_button("Actualizar grupos"):
                    from core.group_board import resize_groups
                    execute(mode, revision, lambda s: resize_groups(s.competitions[cfg.competencia], len(c.teams), groups, cfg.cupos_clasificados), "Grupos actualizados; resultados conservados.")
        st.success(f"Grupos guardados · {cfg.metodo_grupos} · Fase: {cfg.fase_actual}")
        st.write("Distribución: " + cfg.equipos_por_grupo)
        st.caption("Puedes cambiar los grupos conservando los resultados. Administración permite reiniciar la competencia y recuperar datos bloqueados.")
        with st.form("participants_total"):
            value = st.number_input("Total esperado de participantes", min_value=0, value=cfg.numero_participantes)
            cupos = st.selectbox("Cupos para eliminatorias", [2, 4, 8, 16, 32, 64], index=[2, 4, 8, 16, 32, 64].index(cfg.cupos_clasificados), disabled=bool(cfg.sistema == "Tiempos" or c.matches or c.rounds or any(t.estado != "Pendiente" for t in c.teams)))
            if st.form_submit_button("Actualizar total de participantes"):
                def update(s):
                    current = s.competitions[cfg.competencia]
                    current.config.numero_participantes = value
                    current.config.cupos_clasificados = cupos
                execute(mode, revision, update)
        return
    with st.form("configure_groups"):
        a, b = st.columns(2)
        total = a.number_input("Total de equipos esperado", 2, 4096, cfg.numero_equipos)
        groups = b.number_input("Total de grupos", 1, 4096, cfg.numero_grupos)
        participants = a.number_input("Participantes esperados", min_value=0, value=cfg.numero_participantes)
        qualified = b.selectbox("Cupos de clasificación", [2, 4, 8, 16, 32, 64], index=[2, 4, 8, 16, 32, 64].index(cfg.cupos_clasificados), disabled=cfg.sistema == "Tiempos")
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
