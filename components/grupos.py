import streamlit as st

from components.layout import group_cards
from core.grupos import nombre_columna
from core.tournament import clasificar
from services.runtime import execute


def render(c, mode, revision, admin):
    st.header("Grupos")
    st.caption("🟢 Clasificado · 🔴 Eliminado · ⚪ Pendiente")
    group_cards(c)
    if not admin or not c.config.torneo_iniciado:
        return
    if c.matches:
        st.info("La clasificación de grupos está cerrada. Reinicia las eliminatorias para modificarla.")
        return
    st.subheader("Registrar clasificación")
    group = st.selectbox("Grupo", [nombre_columna(i+1) for i in range(c.config.numero_grupos)], format_func=lambda g: f"Grupo {g}")
    for t in [t for t in c.teams if t.grupo == group]:
        with st.container(border=True):
            st.write(f"**{t.nombre_equipo}** · {t.estado}")
            a, b, d = st.columns(3)
            for container, label, status in ((a, "✓ CLASIFICA", "Clasificado"), (b, "✗ NO CLASIFICA", "Eliminado"), (d, "↺ Pendiente", "Pendiente")):
                if container.button(label, key=f"class_{t.id_equipo}_{status}", disabled=t.estado == status):
                    execute(mode, revision, lambda s, tid=t.id_equipo, value=status: clasificar(s.competitions[c.config.competencia], tid, value))
