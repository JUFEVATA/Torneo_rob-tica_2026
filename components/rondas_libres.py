import pandas as pd
import streamlit as st
from core.free_rounds import phases, classify
from core.sheet_flow import TO_PUBLIC, TO_INTERNAL, STATES, PHASE_SHEETS
from services.runtime import execute


def render(c, mode, revision, admin):
    st.header("Rondas de clasificación")
    available = phases(c)
    phase = st.selectbox("Ronda", available, format_func=lambda f: PHASE_SHEETS[f],
                         index=available.index(c.config.fase_actual) if c.config.fase_actual in available else len(available)-1 if c.config.campeon else 0)
    entries = c.rounds.get(phase, {})
    st.caption(f"{len(entries)} equipos · {sum(s == 'Clasificado' for s in entries.values())} clasificados")
    if not entries:
        st.info("Los equipos aparecerán al marcar Clasifica en la fase anterior.")
        return
    if admin:
        with st.form("free_round_" + phase):
            choices = {tid: st.selectbox(c.name(tid), STATES, index=STATES.index(TO_PUBLIC[status]), key=phase+tid)
                       for tid, status in entries.items()}
            if st.form_submit_button("Guardar clasificación", type="primary"):
                def operation(state):
                    from core.free_rounds import reconcile
                    current = state.competitions[c.config.competencia]
                    for tid, status in choices.items():
                        current.rounds[phase][tid] = TO_INTERNAL[status]
                    reconcile(current)
                execute(mode, revision, operation)
    else:
        st.dataframe(pd.DataFrame([{"Equipo": c.name(tid), "Estado": TO_PUBLIC[status]} for tid, status in entries.items()]), hide_index=True, width="stretch")
