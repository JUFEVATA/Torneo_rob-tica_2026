"""Conversión entre el modelo y las pestañas persistentes del libro."""
from dataclasses import asdict, fields
import hashlib
import json

from core.eliminatorias import ORDEN_FASES, partidos_fase
from core.grupos import nombre_columna
from core.models import Competition, Config, Match, State, Team, ValidationError
from core.tournament import validar_estado

HEADERS = {
    "Configuracion": ["competencia", "campo", "valor"],
    "Equipos": [f.name for f in fields(Team)],
    "Grupos": ["Sin grupos"],
    "Rondas": ["competencia", "fase", "id_equipo", "estado"],
    "Reserva": [f.name for f in fields(Team)],
    "Partidos": [f.name for f in fields(Match)] + ["nombre_equipo_1", "nombre_equipo_2", "nombre_ganador"],
    "Clasificados": ["competencia", "fase_destino", "id_equipo", "nombre_equipo", "grupo"],
    "Resultados": ["competencia", "posicion", "id_equipo", "nombre_equipo"],
}
TABS = list(HEADERS)
INT_CONFIG = {"numero_equipos", "numero_grupos", "numero_participantes", "cupos_clasificados"}


def fingerprint(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def boolean(value) -> bool:
    if value is True or str(value).upper() == "TRUE":
        return True
    if value is False or str(value).upper() == "FALSE":
        return False
    raise ValidationError("Los booleanos deben ser TRUE o FALSE.")


def entero(value) -> int:
    if isinstance(value, bool):
        raise ValidationError("Se esperaba un entero, no un booleano.")
    try:
        numero = int(str(value))
    except (ValueError, TypeError):
        raise ValidationError(f"Valor entero inválido: {str(value)[:40]}") from None
    return numero


def records(rows: list[list], tab: str) -> list[dict]:
    if not rows:
        return []
    header = rows[0]
    required = HEADERS[tab]
    if tab == "Partidos":
        required = [f.name for f in fields(Match)]
    if len(header) != len(set(header)) or any(h not in header for h in required):
        raise ValidationError(f"Encabezados inválidos en {tab}. Consulta README.md.")
    return [dict(zip(header, row + [""] * max(0, len(header) - len(row))))
            for row in rows[1:] if any(str(v).strip() for v in row)]


def decode(tables: dict) -> State:
    state, configs = State(), {}
    allowed = {f.name for f in fields(Config)}
    for row in records(tables.get("Configuracion", []), "Configuracion"):
        name, key, value = str(row["competencia"]), str(row["campo"]), row["valor"]
        if key not in allowed:
            raise ValidationError(f"Campo de configuración desconocido: {key}.")
        config = configs.setdefault(name, {})
        if key in config:
            raise ValidationError(f"Campo repetido en Configuracion: {name} / {key}.")
        config[key] = entero(value) if key in INT_CONFIG else boolean(value) if key == "torneo_iniciado" else str(value)
    for name, config in configs.items():
        if config.get("competencia", name) != name:
            raise ValidationError("La competencia de Configuracion es inconsistente.")
        config["competencia"] = name
        try:
            state.competitions[name] = Competition(Config(**config))
        except TypeError:
            raise ValidationError(f"Faltan campos obligatorios en Configuracion para {name}.") from None
    for tab, attribute in (("Equipos", "teams"), ("Reserva", "reserve")):
        for row in records(tables.get(tab, []), tab):
            data = {f.name: str(row[f.name]) for f in fields(Team)}
            data["clasificado"] = boolean(row["clasificado"])
            data["numero_participantes"] = entero(row["numero_participantes"] or 0)
            if data["competencia"] not in state.competitions:
                raise ValidationError("Equipo de una competencia no configurada.")
            getattr(state.competitions[data["competencia"]], attribute).append(Team(**data))
    for row in records(tables.get("Partidos", []), "Partidos"):
        data = {f.name: str(row[f.name]) for f in fields(Match)}
        data["numero_partido"] = entero(row["numero_partido"])
        if data["competencia"] not in state.competitions:
            raise ValidationError("Partido de una competencia no configurada.")
        state.competitions[data["competencia"]].matches.append(Match(**data))
    for row in records(tables.get('Rondas', []),'Rondas'):
        name=str(row['competencia'])
        if name not in state.competitions: raise ValidationError('Competencia desconocida en Rondas.')
        entries=state.competitions[name].rounds.setdefault(str(row['fase']),{})
        tid=str(row['id_equipo'])
        if tid in entries: raise ValidationError('Registro duplicado en Rondas.')
        entries[tid]=str(row['estado'])
    validar_estado(state)
    return state


def clasificados_actuales(c: Competition) -> tuple[str, list[str]]:
    from core.eliminatorias import fase_para
    if c.config.sistema == 'Libre':
        from core.free_rounds import active
        return ('Campeón' if c.config.campeon else c.config.fase_actual), list(active(c))
    if not c.matches:
        return fase_para(c.config.cupos_clasificados), [t.id_equipo for t in c.teams if t.clasificado]
    if c.config.campeon:
        return "Campeón", [c.config.campeon]
    # La ronda siguiente se crea automáticamente: sus participantes son quienes
    # acaban de avanzar, y deben seguir visibles aunque aún no tenga ganadores.
    fase = c.config.fase_actual
    return fase, [team_id for m in partidos_fase(c, fase)
                  for team_id in (m.equipo_1, m.equipo_2) if team_id]


def encode(state: State) -> dict[str, list[list]]:
    tables = {tab: [list(header)] for tab, header in HEADERS.items()}
    columns = []
    for name, c in state.competitions.items():
        for key, value in asdict(c.config).items():
            tables["Configuracion"].append([name, key, value])
        for t in c.teams:
            tables["Equipos"].append(list(asdict(t).values()))
        for phase,entries in c.rounds.items():
            for tid,status in entries.items():tables['Rondas'].append([name,phase,tid,status])
        for t in c.reserve:
            tables["Reserva"].append(list(asdict(t).values()))
        if c.config.torneo_iniciado:
            for index in range(c.config.numero_grupos):
                grupo = nombre_columna(index + 1)
                columns.append([f"Grupo {grupo}", name] + [t.nombre_equipo for t in c.teams if t.grupo == grupo])
        for m in c.matches:
            tables["Partidos"].append(list(asdict(m).values()) +
                                      [c.name(m.equipo_1) if m.equipo_1 else "",
                                       c.name(m.equipo_2) if m.equipo_2 else "",
                                       c.name(m.ganador) if m.ganador else ""])
        fase, clasificados = clasificados_actuales(c)
        for team_id in clasificados:
            t = next(t for t in c.teams if t.id_equipo == team_id)
            tables["Clasificados"].append([name, fase, t.id_equipo, t.nombre_equipo, t.grupo])
        if c.config.sistema == 'Libre':
            if c.config.campeon:tables['Resultados'].append([name,1,c.config.campeon,c.name(c.config.campeon)])
            continue
        if c.config.campeon:
            final = partidos_fase(c, "Final")[0]
            segundo = final.equipo_2 if final.ganador == final.equipo_1 else final.equipo_1
            for posicion, team_id in ((1, c.config.campeon), (2, segundo)):
                tables["Resultados"].append([name, posicion, team_id, c.name(team_id)])
    if columns:
        tables["Grupos"] = [[col[row] if row < len(col) else "" for col in columns]
                             for row in range(max(map(len, columns)))]
    return tables
