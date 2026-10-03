"""Registro del juez y paneles públicos de seguidor de línea."""
from html import escape
import pandas as pd
import streamlit as st
from core import line_racing as racing
from services.runtime import execute
from utils.helpers import csv_seguro


def phase_card(c, phase):
    rows = racing.standings(c, phase)
    if not rows:
        st.info("Los participantes aparecerán al cerrar la fase anterior.")
        return
    items = []
    for row in rows:
        badge = "ok" if row["Estado"] in ("Clasifica", "Podio") else "out" if row["Estado"].startswith(("No clasifica", "Descalificado")) else ""
        detail = str(row["Puesto"]) + '.º puesto' if row["Puesto"] != "—" else "Por registrar" if row["Estado"] == "Pendiente" else "Sin tiempo válido"
        parts = racing.time_parts(row["Mejor tiempo"])
        time_html = '<div class="race-time">' + ''.join('<span><small>' + label + '</small><b>' + (str(part).zfill(digits) if part != "" else '—') + '</b></span>' for label, part, digits in zip(['Minutos', 'Segundos', 'Milisegundos'], parts, [2, 2, 3])) + '</div>' if row["Mejor tiempo"] != "—" else ""
        items.append('<div class="team-row"><div><strong>' + escape(row["Equipo"]) + '</strong><div class="race-detail">' +
                     escape(detail) + '</div>' + time_html + '</div><span class="badge ' + badge + '">' + escape(row["Estado"]) + '</span></div>')
    st.markdown('<div class="group-card phase-card"><div class="group-head">' + escape(racing.LABELS[phase]) +
                '<span class="group-count">' + str(len(rows)) + ' equipos · ' + ('Cerrada' if phase in c.closed_phases else 'En curso') +
                '</span></div><div class="phase-columns">' + ''.join(items) + '</div></div>', unsafe_allow_html=True)


def phases_view(c):
    st.markdown('<div class="race-flow">' + ''.join(
        '<div class="race-step"><strong>' + escape(racing.LABELS[p]) + '</strong><span>' +
        (str(len(c.rounds[p])) + ' equipos' if p in c.rounds else 'Por definir') + '</span><small>' +
        ('Cerrada' if p in c.closed_phases else 'En curso' if p in c.rounds else 'Pendiente') + '</small></div>'
        for p in racing.PHASES) + '</div>', unsafe_allow_html=True)
    phase = st.selectbox("Consultar fase", racing.PHASES, index=racing.PHASES.index(next(reversed(c.rounds), "Linea1")), format_func=racing.LABELS.get)
    phase_card(c, phase)


def render(c, mode, revision):
    st.header("Registro de tiempos")
    st.caption("Tres intentos por fase · máximo 01:30.000 por recorrido · tres fallos nuevos en cada fase · máximo dos integrantes por equipo.")
    with st.expander("Reglas de pista para el juez"):
        st.write("Un robot por equipo. Máximo dos integrantes. Tres intentos en cada fase; cuenta el menor tiempo válido. Tres fallos penalizados en una fase descalifican al equipo. Los fallos al perder la línea o por intervención los registra el juez.")
        st.write("Tiempo de reparación previo a la ronda: un minuto. Presentación: un minuto de tolerancia; después, el juez registra No presentó. Espera de salida: dos segundos. Estas esperas no se suman al tiempo del recorrido. Los jueces deciden sanciones y empates.")
    phases = list(c.rounds)
    if not phases:
        st.info("Completa los equipos y genera los grupos desde Configuración para iniciar.")
        return
    phase = st.selectbox("Fase a registrar", phases, index=len(phases)-1, format_func=racing.LABELS.get)
    with st.expander("Consultar clasificación de esta fase"):
        phase_card(c, phase)
    ids = list(c.rounds[phase])
    tid = st.selectbox("Equipo a cronometrar", ids, format_func=c.name)
    record = c.timing[phase][tid]
    with st.form("race_record_" + phase + "_" + tid + "_" + revision):
        attempts = []
        for index, value in enumerate(record["intentos"], 1):
            st.markdown("**Intento " + str(index) + "**")
            columns = st.columns([2, 1, 1, 1])
            choices = ["Pendiente", "Tiempo", *racing.FAILED]
            choice = "Pendiente" if not value else value if value in racing.FAILED else "Tiempo"
            outcome = columns[0].selectbox(f"Resultado intento {index}", choices, index=choices.index(choice))
            ms = racing.parse_time(value) or 0
            minutes = columns[1].number_input(f"Minutos intento {index}", 0, 59, ms//60000)
            seconds = columns[2].number_input(f"Segundos intento {index}", 0, 59, ms//1000%60)
            millis = columns[3].number_input(f"Milisegundos intento {index}", 0, 999, ms%1000)
            attempts.append(racing.format_time(racing.milliseconds(minutes, seconds, millis)) if outcome == "Tiempo" else "" if outcome == "Pendiente" else outcome)
        left, right = st.columns(2)
        faults = left.number_input("Fallos penalizados en esta fase", 0, 3, record["fallos"])
        sanction = right.selectbox("Decisión del juez", racing.SANCTIONS, index=racing.SANCTIONS.index(record["sancion"]))
        order = left.number_input("Orden de desempate del juez (0 sin desempate)", 0, 4096, record["desempate"])
        st.caption("Registra los fallos que penalice el juez. No se añaden segundos de sanción. Los tiempos superiores a 90 segundos no cuentan. Una corrección recalcula las fases siguientes.")
        if st.form_submit_button("Guardar tiempos", type="primary"):
            updated = {"intentos": attempts, "fallos": faults, "sancion": sanction, "desempate": order}
            execute(mode, revision, lambda s: racing.set_record(s.competitions[c.config.competencia], phase, tid, updated), "Tiempos guardados; clasificación recalculada.")
    with st.form("race_close_" + phase):
        st.write("Avanzan los " + str(racing.CAPACITIES[phase]) + " mejores tiempos válidos." if phase != "Linea4" else "Los tres mejores tiempos válidos definen el podio.")
        confirm = st.checkbox("Confirmo que los tiempos de esta fase son definitivos")
        if st.form_submit_button("Cerrar fase y clasificar", type="primary", disabled=phase in c.closed_phases):
            def close(state):
                if not confirm:
                    from core.models import ValidationError
                    raise ValidationError("Confirma los tiempos antes de cerrar la fase.")
                racing.close_phase(state.competitions[c.config.competencia], phase)
            execute(mode, revision, close, "Fase cerrada; participantes de la siguiente fase actualizados.")


def history(c):
    rows = []
    for phase in racing.PHASES:
        current = {r["id"]: r for r in racing.standings(c, phase)}
        for tid, record in c.timing.get(phase, {}).items():
            result = current.get(tid, {})
            entry = {"Fase": racing.LABELS[phase], "Equipo": c.name(tid)}
            for i, attempt in enumerate(record["intentos"], 1):
                entry.update({f"Intento {i} · {unit}": part for unit, part in zip(['Minutos', 'Segundos', 'Milisegundos'], racing.time_parts(attempt))})
                entry[f"Resultado intento {i}"] = attempt if attempt in racing.FAILED else "Tiempo" if attempt else "Pendiente"
            entry.update({"Mejor tiempo · " + unit: part for unit, part in zip(['Minutos', 'Segundos', 'Milisegundos'], racing.time_parts(result.get("Mejor tiempo", "—")))})
            entry.update({"Fallos": record["fallos"], "Sanción": record["sancion"], "Resultado": result.get("Estado", "Fuera de la selección actual")})
            rows.append(entry)
    frame = pd.DataFrame(rows)
    st.dataframe(frame, hide_index=True, width="stretch")
    st.download_button("Descargar historial CSV", csv_seguro(frame), "historial-linea.csv", "text/csv")
