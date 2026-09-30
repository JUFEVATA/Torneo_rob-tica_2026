import streamlit as st

from components.layout import champion
from core.eliminatorias import ORDEN_FASES, actualizar_ganador, partidos_fase
from core.publication import LABELS
from services.runtime import execute


def render(c, mode, revision, admin):
    st.header("Eliminatorias")
    if not c.matches:
        st.info("Completa los cupos en Grupos y genera el cuadro desde Clasificados.")
        return
    champion(c)
    phases = [f for f in ORDEN_FASES if partidos_fase(c, f)]
    default = c.config.fase_actual if c.config.fase_actual in phases else phases[-1]
    phase = st.selectbox("Ronda", phases, index=phases.index(default), format_func=lambda f: LABELS[f])
    matches = partidos_fase(c, phase)
    st.caption(f"{sum(bool(m.ganador) for m in matches)} / {len(matches)} partidos finalizados")
    earlier_pending = any(not m.ganador for m in c.matches if ORDEN_FASES.index(m.fase) < ORDEN_FASES.index(phase))
    for m in matches:
        with st.container(border=True):
            st.caption(f"PARTIDO {m.numero_partido:02d} · {m.estado.upper()}")
            st.subheader(f"{c.name(m.equipo_1)}  vs  {c.name(m.equipo_2)}")
            if m.ganador:
                st.success(f"Ganador: {c.name(m.ganador)}")
            if not admin:
                continue
            if not m.ganador:
                a, b = st.columns(2)
                for col, team_id in ((a, m.equipo_1), (b, m.equipo_2)):
                    if col.button(f"{c.name(team_id)} gana", key=f"win_{m.id_partido}_{col is a}", disabled=earlier_pending or not m.equipo_1 or not m.equipo_2):
                        execute(mode, revision, lambda s, mid=m.id_partido, tid=team_id: actualizar_ganador(s.competitions[c.config.competencia], mid, tid))
            else:
                with st.expander("Corregir resultado"):
                    st.warning("Este cambio afecta fases posteriores. Se borrarán los resultados de los cruces que cambien; los demás se conservarán.")
                    with st.form(f"correction_{m.id_partido}"):
                        chosen = st.selectbox("Resultado corregido", ["", m.equipo_1, m.equipo_2], format_func=lambda tid: c.name(tid) if tid else "Quitar ganador", index=["", m.equipo_1, m.equipo_2].index(m.ganador))
                        confirm = st.checkbox("Confirmo la corrección y sus efectos en las fases posteriores")
                        if st.form_submit_button("Aplicar corrección"):
                            if not confirm:
                                st.error("Marca la confirmación para aplicar este cambio.")
                            else:
                                execute(mode, revision, lambda s, mid=m.id_partido: actualizar_ganador(s.competitions[c.config.competencia], mid, chosen, True))
