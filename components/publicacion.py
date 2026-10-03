import streamlit as st
from core.publication import public_name, publish, podium, save_podium, stages_for, LABELS
from services.runtime import execute


def render(state, c, mode, revision):
    st.header("Publicación")
    current = public_name(state)
    st.caption(f"El público está viendo: {current or 'Sin competencia'}")
    names = list(state.competitions)
    name = st.selectbox("Competencia para el público", names, index=names.index(c.config.competencia))
    target = state.competitions[name]
    with st.form("public_settings"):
        options = ["", *stages_for(target)]
        phase = st.selectbox("Etapa visible en Inicio", options, index=options.index(target.config.etapa_publica), key="publish_stage_" + name,
                             format_func=lambda f: "Automática según clasificaciones" if not f else LABELS[f])
        st.caption("La etapa manual cambia la presentación. Los resultados se gestionan en Registro de tiempos o Resultados.")
        if st.form_submit_button("Publicar competencia y etapa", type="primary"):
            execute(mode, revision, lambda s: publish(s, name, phase), "Publicación actualizada para todos los visitantes.")


def edit_podium(c, mode, revision):
    st.subheader("Editar puestos")
    with st.form("podium_settings"):
        ids = ["", *[t.id_equipo for t in c.teams]]
        result = podium(c)
        selections = [st.selectbox(label, ids, index=ids.index(result[pos]),
                                   format_func=lambda tid: c.name(tid) if tid else "Por definir")
                      for pos, label in [(1, "Primer puesto"), (2, "Segundo puesto"), (3, "Tercer puesto")]]
        if st.form_submit_button("Guardar podio", type="primary"):
            execute(mode, revision, lambda s: save_podium(s.competitions[c.config.competencia], *selections), "Podio actualizado.")
