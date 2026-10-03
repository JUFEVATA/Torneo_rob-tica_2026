import streamlit as st

from core.models import Config
from core.tournament import configurar, crear_competencia_lista, iniciar_grupos
from services.runtime import execute


def create_form(state, mode, revision):
    with st.expander("Crear una competencia", expanded=not state.competitions):
        kind = st.selectbox("Tipo de competencia", ["Selecciona el tipo", "Seguidor de línea por tiempos", "Clasificación libre"], key="new_competition_kind")
        if kind == "Selecciona el tipo":
            st.caption("Elige el tipo para preparar sus grupos y hojas de resultados.")
            return
        timed = kind == "Seguidor de línea por tiempos"
        st.caption("Se habilitan las cuatro hojas de tiempos con columnas MM, SS y MS." if timed else "Se habilitan los grupos y las rondas con selección libre de clasificados.")
        with st.form("new_competition", clear_on_submit=True):
            name = st.text_input("Nombre de la competencia", placeholder="Seguidor de línea" if timed else "Sumo")
            left, right = st.columns(2)
            total = left.number_input("Cantidad total de equipos", 2, 4096, 32)
            groups = right.number_input("Cantidad de grupos", 1, 4096, 4)
            participants = left.number_input("Cantidad total de participantes", min_value=0, value=0)
            qualified = 16 if timed else right.selectbox("Equipos que avanzan", [2, 4, 8, 16, 32, 64], index=3)
            names = st.text_area("Equipos (uno por línea, opcional)", placeholder="Escribe los nombres o déjalo vacío para usar Equipo 1, Equipo 2…")
            st.caption("Los espacios sin nombre se completan con equipos editables. Al crear, los grupos quedan listos.")
            if st.form_submit_button("Crear competencia y grupos", type="primary"):
                cap = min(16, max(n for n in (2, 4, 8, 16, 32, 64) if n <= total)) if timed else qualified
                cfg = Config(name, total, groups, participants, cap, sistema="Tiempos" if timed else "Libre")
                execute(mode, revision, lambda s: crear_competencia_lista(s, cfg, [n.strip() for n in names.splitlines() if n.strip()]),
                        "Competencia creada con equipos, grupos y hojas de resultados listas.", select_competition=name)


def render(state, c, mode, revision, admin):
    if not admin:
        return
    st.header("Configuración")
    create_form(state, mode, revision)
    import_form(mode, revision)
    if not c:
        return
    cfg = c.config
    st.subheader(cfg.competencia)
    timed = cfg.sistema == "Tiempos"
    st.caption("Seguidor de línea por tiempos · 16 → 8 → 4 → podio · tres intentos y tres fallos nuevos por fase." if timed else "Clasificación libre" if cfg.sistema == "Libre" else "Enfrentamientos")
    with st.form("competition_settings_" + cfg.competencia):
        a, b = st.columns(2)
        locked = bool(c.matches or any(t.estado != "Pendiente" for t in c.teams) or c.closed_phases or any(any(r["intentos"]) or r["fallos"] or r["sancion"] != "Sin sanción" for phase in c.timing.values() for r in phase.values()))
        total = a.number_input("Cantidad de equipos", 2, 4096, cfg.numero_equipos, disabled=locked)
        groups = b.number_input("Cantidad de grupos", 1, 4096, cfg.numero_grupos)
        participants = a.number_input("Total esperado de participantes", min_value=0, value=cfg.numero_participantes)
        cupos = cfg.cupos_clasificados if timed else b.selectbox("Equipos que avanzan", [2,4,8,16,32,64], index=[2,4,8,16,32,64].index(cfg.cupos_clasificados), disabled=locked)
        method = st.selectbox("Distribución", ["Orden original", "Sorteo aleatorio"], index=int(cfg.metodo_grupos == "Sorteo aleatorio"))
        if c.reserve:
            st.caption(f"{len(c.reserve)} equipos en reserva; se recuperan al aumentar el total.")
        if locked:
            st.caption("Puedes cambiar los grupos conservando los resultados. Para cambiar el total, reinicia los resultados desde Administración.")
        label = "Guardar cambios" if cfg.torneo_iniciado else "Guardar y generar grupos"
        if st.form_submit_button(label, type="primary"):
            def save(s):
                current = s.competitions[cfg.competencia]
                if current.config.torneo_iniciado:
                    from core.group_board import resize_groups
                    resize_groups(current, total, groups, cupos, method == "Sorteo aleatorio")
                    current.config.numero_participantes = participants
                else:
                    configurar(current, total, groups, participants, cupos)
                    iniciar_grupos(current, method == "Sorteo aleatorio", genericos=True)
            execute(mode, revision, save, "Configuración y grupos guardados.")
    if cfg.torneo_iniciado:
        st.caption(f"{len(c.teams)} equipos · {cfg.numero_grupos} grupos · Distribución: {cfg.equipos_por_grupo}")


def import_form(mode, revision):
    with st.expander("Importar una lista con grupos ya asignados"):
        with st.form("import_groups"):
            text = st.text_area("Lista completa", height=250, placeholder="Competencia: Sumo\nParticipantes: 8 | Grupos: 2\nGrupo A\n• Nombre del equipo")
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
