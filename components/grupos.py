import streamlit as st

from components.layout import group_cards
from core.grupos import nombre_columna
from core.tournament import clasificar, iniciar_eliminatorias
from services.runtime import execute


def render(c, mode, revision, admin):
    st.header("Grupos")
    st.caption("🟢 Clasificado · 🔴 Eliminado · ⚪ Pendiente")
    group_cards(c)
    if not admin or not c.config.torneo_iniciado:
        return
    if c.config.sistema == "Tiempos":
        st.info("Estos grupos organizan la inscripción. Registra hasta tres intentos en Registro de tiempos para clasificar.")
        return
    st.subheader("Registrar clasificación")
    group = st.selectbox("Grupo", [nombre_columna(i+1) for i in range(c.config.numero_grupos)], format_func=lambda g: f"Grupo {g}")
    for t in [t for t in c.teams if t.grupo == group]:
        with st.container(border=True):
            st.write(f"**{t.nombre_equipo}** · {t.estado}")
            labels = {"Pendiente": "Pendiente", "Clasifica": "Clasificado", "No clasifica": "Eliminado"}
            selected = st.selectbox("Estado de " + t.nombre_equipo, list(labels),
                                    index=list(labels.values()).index(t.estado),
                                    key=f"class_{t.id_equipo}_{revision}", label_visibility="collapsed")
            if labels[selected] != t.estado:
                def operation(s, tid=t.id_equipo, value=labels[selected]):
                    current = s.competitions[c.config.competencia]
                    clasificar(current, tid, value)
                    if not current.matches and all(team.estado != "Pendiente" for team in current.teams) and sum(team.clasificado for team in current.teams) == current.config.cupos_clasificados:
                        iniciar_eliminatorias(current)
                execute(mode, revision, operation)
