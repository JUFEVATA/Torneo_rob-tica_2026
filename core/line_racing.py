"""Seguidor de línea: cuatro fases por mejor tiempo, sin enfrentamientos."""
from copy import deepcopy
import re
from core.models import ValidationError

PHASES = ["Linea1", "Linea2", "Linea3", "Linea4"]
LABELS = dict(zip(PHASES, ["Fase 1 · Clasificatoria", "Fase 2 · Mejores 16", "Fase 3 · Mejores 8", "Fase 4 · Final"]))
SHEETS = dict(zip(PHASES, ["SL Fase 1", "SL Fase 2", "SL Fase 3", "SL Final"]))
CAPACITIES = dict(zip(PHASES, [16, 8, 4, 3]))
FAILED = ("Fallo", "No terminó", "No presentó")
SANCTIONS = ("Sin sanción", "No presentó", "Descalificado")
LEGACY_HEADER = ["Equipo", "Intento 1", "Intento 2", "Intento 3", "Fallos", "Sanción", "Desempate del juez", "Mejor tiempo", "Puesto", "Resultado", "id_equipo", "competencia"]
ATTEMPT_COLS = (3, 6, 9)
BEST_COL = 12
OUTCOME_COLS = (15, 16, 17)
FAULT_COL, SANCTION_COL, TIE_COL, PLACE_COL, RESULT_COL, ID_COL, COMP_COL = range(18, 25)
HEADER_ROWS = 4
OUTCOMES = ("Pendiente", "Tiempo", *FAILED)
HEADER = ["", "", "", *(["MM", "SS", "MS"] * 4), *([""] * 8), "id_equipo", "competencia"]
GROUP_HEADER = ["N.º", "Grupo", "Equipo", "INTENTO 1", "", "", "INTENTO 2", "", "", "INTENTO 3", "", "", "MEJOR TIEMPO", "", "", "Resultado intento 1", "Resultado intento 2", "Resultado intento 3", "Fallos", "Sanción", "Orden empate", "Puesto", "Estado", "id_equipo", "competencia"]


def capacities(c):
    """Cantidad de clasificados después de cada fase de tiempos."""
    first = 32 if getattr(c.config, "cupos_clasificados", 16) >= 32 else 16
    return dict(zip(PHASES, [first, first // 2, first // 4, 4 if first == 32 else 3]))


def capacity(c, phase):
    return capacities(c)[phase]


def milliseconds(minutes, seconds, millis):
    if any(type(v) is not int for v in (minutes, seconds, millis)) or not 0 <= minutes <= 59 or not 0 <= seconds < 60 or not 0 <= millis < 1000:
        raise ValidationError("Usa minutos de 0 a 59, segundos de 0 a 59 y milisegundos de 0 a 999.")
    return minutes * 60000 + seconds * 1000 + millis


def format_time(ms):
    return f"{ms//60000:02d}:{ms//1000%60:02d}.{ms%1000:03d}" if ms is not None else "—"


def parse_time(value):
    text = str(value).strip()
    if not text or text in FAILED:
        return None
    match = re.fullmatch(r"(\d{1,2}):(\d{2})[.,](\d{3})", text)
    if not match:
        raise ValidationError("Escribe el tiempo como mm:ss.mmm, por ejemplo 01:02.345; deja vacío un intento pendiente o escribe No terminó.")
    result = milliseconds(*map(int, match.groups()))
    if result == 0:
        raise ValidationError("Un recorrido válido debe tener un tiempo mayor que cero.")
    return result


def blank_record():
    return {"intentos": ["", "", ""], "fallos": 0, "sancion": "Sin sanción", "desempate": 0}


def validate_record(record):
    if set(record) != {"intentos", "fallos", "sancion", "desempate"} or not isinstance(record["intentos"], list) or len(record["intentos"]) != 3:
        raise ValidationError("Cada equipo debe tener exactamente tres intentos.")
    for time in record["intentos"]:
        parse_time(time)
    if type(record["fallos"]) is not int or not 0 <= record["fallos"] <= 3:
        raise ValidationError("Los fallos penalizados deben ser de 0 a 3.")
    if record["sancion"] not in SANCTIONS:
        raise ValidationError("Sanción desconocida; selecciona una decisión del juez.")
    if type(record["desempate"]) is not int or not 0 <= record["desempate"] <= 4096:
        raise ValidationError("El orden de desempate debe ser un entero no negativo.")


def faults(c, phase, tid):
    stages = [phase] if c.config.regla_fallos == "Por fase" else PHASES[:PHASES.index(phase)+1]
    return sum(c.timing.get(p, {}).get(tid, {}).get("fallos", 0) for p in stages)


def best(c, phase, tid):
    record = c.timing[phase][tid]
    if record["sancion"] != "Sin sanción" or faults(c, phase, tid) >= 3:
        return None
    times = [parse_time(t) for t in record["intentos"]]
    valid = [t for t in times if t is not None and t <= 90000]
    return min(valid) if valid else None


def rank(c, phase, incoming=None):
    ids = list(c.rounds.get(phase, {})) if incoming is None else list(incoming)
    eligible = [tid for tid in ids if best(c, phase, tid) is not None]
    return sorted(eligible, key=lambda tid: (best(c, phase, tid), c.timing[phase][tid]["desempate"] or 4097, c.name(tid).casefold()))


def closing_error(c, phase, incoming):
    for tid in incoming:
        record = c.timing[phase][tid]
        finished = record["sancion"] != "Sin sanción" or faults(c, phase, tid) >= 3 or any(str(t).strip() for t in record["intentos"])
        if not finished:
            return f"Faltan intentos o la decisión del juez para {c.name(tid)}."
    ranking = rank(c, phase, incoming)
    cap = capacity(c, phase)
    for time in {best(c, phase, tid) for tid in ranking}:
        group = [tid for tid in ranking if best(c, phase, tid) == time]
        first = ranking.index(group[0])
        affects = len(group) > 1 and ((first < cap < first + len(group)) or (phase == "Linea4" and first < 3))
        orders = [c.timing[phase][tid]["desempate"] for tid in group]
        if affects and (not all(orders) or len(orders) != len(set(orders))):
            return f"Empate en {format_time(time)} que afecta la clasificación o el podio. El juez debe asignar órdenes de desempate distintos, empezando en 1."
    return ""


def reconcile(c):
    registered = {t.id_equipo for t in c.teams}
    if c.matches or any(t.clasificado or t.estado != "Pendiente" for t in c.teams):
        raise ValidationError("Seguidor de línea clasifica por tiempos, no con los desplegables de grupos.")
    for phase, records in c.timing.items():
        if phase not in PHASES:
            raise ValidationError("Fase de tiempos desconocida.")
        for tid in list(records):
            if tid not in registered:
                records.pop(tid)
            else:
                validate_record(records[tid])
    incoming = [t.id_equipo for t in c.teams] if c.config.torneo_iniciado else []
    closed, rounds = [], {}
    old_closed = list(c.closed_phases)
    for phase in PHASES:
        if not incoming:
            break
        records = c.timing.setdefault(phase, {})
        # Con una nueva selección, retirar solo los tiempos de quienes ya no participan.
        for tid in list(records):
            if tid not in incoming:
                records.pop(tid)
        for tid in incoming:
            records.setdefault(tid, blank_record())
        rounds[phase] = {tid: "Eliminado" if faults(c, phase, tid) >= 3 or records[tid]["sancion"] != "Sin sanción" else "Pendiente" for tid in incoming}
        if phase not in old_closed or closing_error(c, phase, incoming):
            break
        winners = rank(c, phase, incoming)[:capacity(c, phase)]
        rounds[phase] = {tid: "Clasificado" if tid in winners else "Eliminado" for tid in incoming}
        closed.append(phase)
        incoming = winners
    c.rounds, c.closed_phases = rounds, closed
    final = rank(c, "Linea4") if "Linea4" in closed else []
    c.config.campeon = final[0] if final else ""
    c.config.fase_actual = "Finalizado" if "Linea4" in closed else next(reversed(rounds)) if rounds else "Inscripción"


def set_record(c, phase, tid, record):
    if tid not in c.rounds.get(phase, {}):
        raise ValidationError("El equipo no participa actualmente en esta fase.")
    validate_record(record)
    c.timing[phase][tid] = deepcopy(record)
    reconcile(c)


def close_phase(c, phase):
    if not c.rounds.get(phase):
        raise ValidationError("La fase no tiene participantes; completa y cierra la anterior.")
    error = closing_error(c, phase, list(c.rounds[phase]))
    if error:
        raise ValidationError(error)
    if phase not in c.closed_phases:
        c.closed_phases.append(phase)
    reconcile(c)


def status(c, phase, tid):
    record = c.timing[phase][tid]
    if record["sancion"] != "Sin sanción":
        return record["sancion"]
    if faults(c, phase, tid) >= 3:
        return "Descalificado · 3 fallos"
    if phase in c.closed_phases:
        return "Podio" if phase == "Linea4" and c.rounds[phase][tid] == "Clasificado" else "Clasifica" if c.rounds[phase][tid] == "Clasificado" else "No clasifica"
    if best(c, phase, tid) is not None:
        return "Tiempo registrado"
    return "Sin tiempo válido" if all(str(t).strip() for t in record["intentos"]) else "Pendiente"


def standings(c, phase):
    ordered = rank(c, phase)
    other = [tid for tid in c.rounds.get(phase, {}) if tid not in ordered]
    result = []
    for tid in ordered + other:
        record = c.timing[phase][tid]
        place = ordered.index(tid)+1 if tid in ordered else "—"
        # Empates no resueltos se muestran como iguales; el nombre no decide el avance.
        if tid in ordered and not record["desempate"]:
            place = 1 + sum(best(c, phase, t) < best(c, phase, tid) for t in ordered)
        result.append({"Puesto": place, "Equipo": c.name(tid), "Mejor tiempo": format_time(best(c, phase, tid)), "Estado": status(c, phase, tid), "id": tid})
    return result


def validate(c):
    if any(t.numero_participantes > 2 for t in c.teams):
        raise ValidationError("Seguidor de línea permite máximo dos integrantes por equipo.")
    if len(set(c.closed_phases)) != len(c.closed_phases) or any(p not in PHASES for p in c.closed_phases):
        raise ValidationError("Cierres de fase inválidos.")
    expected = deepcopy(c)
    reconcile(expected)
    if (expected.rounds, expected.closed_phases, expected.timing, expected.config.fase_actual, expected.config.campeon) != (c.rounds, c.closed_phases, c.timing, c.config.fase_actual, c.config.campeon):
        raise ValidationError("Los tiempos y las fases no coinciden con las clasificaciones anteriores.")


def reset(c, scope):
    if scope == "Competencia completa":
        c.teams.clear(); c.reserve.clear(); c.timing.clear(); c.closed_phases.clear(); c.rounds.clear()
        c.config.torneo_iniciado = False; c.config.equipos_por_grupo = ""
    elif scope == "Eliminatorias":
        for phase in PHASES[1:]: c.timing.pop(phase, None)
        c.closed_phases = [p for p in c.closed_phases if p == "Linea1"]
    elif scope == "Fase actual":
        phase = "Linea4" if c.config.fase_actual == "Finalizado" else c.config.fase_actual
        if phase in PHASES:
            for p in PHASES[PHASES.index(phase):]: c.timing.pop(p, None)
            c.closed_phases = [p for p in c.closed_phases if PHASES.index(p) < PHASES.index(phase)]
    else:
        raise ValidationError("Alcance de reinicio inválido.")
    reconcile(c)


def time_parts(value):
    """Componentes numéricos; nunca horas del día ni fracciones de fecha."""
    ms = None if value == "—" else parse_time(value)
    return [ms // 60000, ms // 1000 % 60, ms % 1000] if ms is not None else ["", "", ""]


def attempt_from_cells(parts, outcome):
    if outcome not in OUTCOMES:
        raise ValidationError("Selecciona un resultado válido para cada intento.")
    if outcome in FAILED:
        return outcome
    if all(v == "" or v is None for v in parts):
        return ""
    if any(v == "" or v is None for v in parts):
        raise ValidationError("Completa las tres columnas del intento: minutos, segundos y milisegundos, incluidos los ceros.")
    values = []
    for v in parts:
        if isinstance(v, bool) or not re.fullmatch(r"\d+", str(v).strip()) and not (isinstance(v, float) and v.is_integer()):
            raise ValidationError("Minutos, segundos y milisegundos deben ser números enteros.")
        values.append(int(v))
    value = format_time(milliseconds(*values))
    parse_time(value)  # Cero no representa un recorrido válido.
    return value


def sheet_rows(state, phase):
    rows = [["SEGUIDOR DE LÍNEA · " + LABELS[phase]], ["MM = minutos · SS = segundos · MS = milisegundos. Registra los intentos disponibles, incluidos los ceros; deja vacíos los que no se realicen. Límite: 01 | 30 | 000."], list(GROUP_HEADER), list(HEADER)]
    for name, c in state.competitions.items():
        if c.config.sistema != "Tiempos": continue
        rows += [["Competencia: " + name], ["Estado de fase", "", "", "Cerrada" if phase in c.closed_phases else "Abierta"]]
        ranking = {row["id"]: row for row in standings(c, phase)}
        for number, tid in enumerate(c.rounds.get(phase, {}), 1):
            record, result = c.timing[phase][tid], ranking[tid]
            team = next(t for t in c.teams if t.id_equipo == tid)
            outcomes = [v if v in FAILED else "Tiempo" if v else "Pendiente" for v in record["intentos"]]
            parts = [part for attempt in record["intentos"] for part in time_parts(attempt)]
            rows.append([number, team.grupo, c.name(tid), *parts, *time_parts(result["Mejor tiempo"]), *outcomes, record["fallos"], record["sancion"], record["desempate"], result["Puesto"], result["Estado"], tid, name])
    return rows


def apply_sheet_phase(updated, previous, rows, phase):
    from services.serialization import entero
    found, controls = {}, {}
    section = None
    split = len(rows) > 3 and rows[3] == HEADER
    id_col, comp_col = (ID_COL, COMP_COL) if split else (10, 11)
    for row in rows:
        if row and str(row[0]).startswith("Competencia: "):
            section = str(row[0])[13:]
            if section not in previous.competitions or previous.competitions[section].config.sistema != "Tiempos":
                raise ValidationError("No cambies los encabezados de competencia en las hojas de tiempos.")
        elif row and row[0] == "Estado de fase" and section:
            control_col = 3 if split else 1
            value = row[control_col] if len(row) > control_col else ""
            if value not in ("Abierta", "Cerrada") or section in controls:
                raise ValidationError("Estado de fase inválido o duplicado.")
            controls[section] = value
        elif section and len(row) > id_col and row[id_col] and row[id_col] != "id_equipo":
            row = row + [""] * max(0, comp_col+1-len(row))
            name, tid = str(row[comp_col]), str(row[id_col])
            if name != section or name not in previous.competitions or tid not in previous.competitions[name].rounds.get(phase, {}) or (name, tid) in found:
                raise ValidationError("Registro de tiempo duplicado o ID modificado.")
            if split:
                attempts = [attempt_from_cells(row[col:col+3], str(row[out])) for col, out in zip(ATTEMPT_COLS, OUTCOME_COLS)]
                record = {"intentos": attempts, "fallos": entero(row[FAULT_COL] or 0), "sancion": str(row[SANCTION_COL]), "desempate": entero(row[TIE_COL] or 0)}
            else:
                # Compatibilidad con las hojas anteriores durante la migración.
                record = {"intentos": [str(row[i] or "").strip() for i in (1, 2, 3)], "fallos": entero(row[4] or 0), "sancion": str(row[5]), "desempate": entero(row[6] or 0)}
            validate_record(record)
            found[name, tid] = record
    expected = {(name, tid) for name, c in previous.competitions.items() if c.config.sistema == "Tiempos" for tid in c.rounds.get(phase, {})}
    # Encabezados recién creados, sin participantes: se generan al sincronizar.
    if rows and len(rows) <= (HEADER_ROWS if split else 3) and not found: return
    if set(found) != expected:
        raise ValidationError("Faltan equipos de tiempos. No borres filas ni las columnas ocultas.")
    for name, c in updated.competitions.items():
        if c.config.sistema != "Tiempos": continue
        old = previous.competitions.get(name)
        if old is None: continue
        for tid in c.rounds.get(phase, {}):
            record = found.get((name, tid))
            if record is not None and record != old.timing.get(phase, {}).get(tid):
                c.timing[phase][tid] = record
        reconcile(c)
        control = controls.get(name)
        if control == "Cerrada" and phase not in old.closed_phases:
            close_phase(c, phase)
        elif control == "Abierta" and phase in old.closed_phases:
            c.closed_phases = [p for p in c.closed_phases if PHASES.index(p) < PHASES.index(phase)]
            reconcile(c)
