"""Formato editable para Sheets: listado inicial y una pestaña por ronda.

La lógica es pura. El repositorio decide cuándo persistir una importación completa.
"""
from copy import deepcopy
from dataclasses import dataclass, field
import re

from core.group_board import MARKER, board_rows, parse_board, resize_groups
from core.models import Competition, Config, State, Team, ValidationError, new_id
from core.grupos import distribuir, nombre_columna
from core.tournament import normalizar, validar_estado, iniciar_eliminatorias
from core.eliminatorias import FASES, ORDEN_FASES, partidos_fase, actualizar_ganador

PHASE_SHEETS = {'Treintaidosavos': '32 avos', 'Dieciseisavos': '16 avos',
                'Octavos': '8vos', 'Cuartos': '4tos', 'Semifinal': 'Semifinal', 'Final': 'Final'}
STAGE_TABS = list(PHASE_SHEETS.values())
STATES = ['Pendiente', 'Clasifica', 'No clasifica']
TO_PUBLIC = {'Pendiente': 'Pendiente', 'Clasificado': 'Clasifica', 'Eliminado': 'No clasifica'}
TO_INTERNAL = {v: k for k, v in TO_PUBLIC.items()}


def normalized_rows(rows):
    cleaned = [list(row) for row in rows]
    for row in cleaned:
        while row and row[-1] == '':
            row.pop()
    while cleaned and not cleaned[-1]:
        cleaned.pop()
    return cleaned


@dataclass
class Roster:
    name: str
    title: str = 'Equipo STEM 2026'
    date: str = ''
    participants: int = 0
    groups: int = 0
    # nombre, grupo, estado visible, ID opcional estable
    entries: list[tuple[str, str, str, str]] = field(default_factory=list)


def parse_rosters(rows: list[list]) -> list[Roster]:
    """Admite texto completo en A1, una línea por celda y estados en B.

    Un boletín nunca se convierte en datos parciales: se valida completo antes de
    reemplazar una competencia. Las líneas desconocidas son errores explícitos.
    """
    # Pegar el boletín completo dentro de A1 reemplaza el bloque anterior.
    if rows and rows[0] and '\n' in str(rows[0][0]) and 'Competencia:' in str(rows[0][0]):
        rows = [[rows[0][0]]]
    result, current, group, title = [], None, '', 'Equipo STEM 2026'
    for row in rows:
        value = str(row[0]).strip() if row else ''
        if not value:
            continue
        lines = value.splitlines()
        for line in lines:
            line = line.strip()
            lower = line.casefold()
            if not line:
                continue
            if lower.startswith('torneos de rob'):
                current, group, title = None, '', 'Equipo STEM 2026'
                continue
            if lower.startswith('competencia:'):
                name = line.split(':', 1)[1].strip()
                if not name:
                    raise ValidationError('Escribe un nombre después de Competencia:.')
                current = Roster(name, title)
                result.append(current)
                group = ''
                continue
            if current is None:
                if lower.startswith('pega ') or lower in ('equipo', 'estado', 'sin grupos') or lower.startswith('grupo '):
                    continue
                title = line
                continue
            if lower.startswith('fecha:'):
                current.date = line.split(':', 1)[1].strip()
                continue
            if lower.startswith('participantes:'):
                match = re.fullmatch(r'Participantes:\s*(\d+)\s*\|\s*Grupos:\s*(\d+)', line, re.I)
                if not match:
                    raise ValidationError('Usa Participantes: 85 | Grupos: 4 en el encabezado.')
                current.participants, current.groups = map(int, match.groups())
                continue
            section = re.fullmatch(r'(?:Equipo|Grupo)\s+(\d+|[A-Z]+)', line, re.I)
            if section and not (len(row) > 2 and row[2]):
                token = section[1]
                group = nombre_columna(int(token)) if token.isdigit() else token.upper()
                continue
            if lower in ('equipo', 'nombre del equipo', 'estado'):
                continue
            if not group:
                raise ValidationError(f'Falta el encabezado Equipo 1 / Grupo A antes de: {line[:60]}.')
            name = re.sub(r'^[•●▪\-]\s*', '', line).strip().replace('\\_', '_')
            status = str(row[1]).strip() if len(lines) == 1 and len(row) > 1 else ''
            status = status or 'Pendiente'
            if status not in STATES:
                raise ValidationError(f'{name}: el estado debe ser Pendiente, Clasifica o No clasifica.')
            team_id = str(row[2]).strip() if len(lines) == 1 and len(row) > 2 else ''
            current.entries.append((name, group, status, team_id))
    seen = set()
    for roster in result:
        key = normalizar(roster.name)
        if key in seen:
            raise ValidationError(f'Competencia repetida en Grupos: {roster.name}.')
        seen.add(key)
        if not roster.groups or len(roster.entries) < 2:
            raise ValidationError(f'{roster.name}: faltan grupos o equipos en el listado.')
        counts = distribuir(len(roster.entries), roster.groups)
        actual = [sum(e[1] == nombre_columna(i + 1) for e in roster.entries) for i in range(roster.groups)]
        if actual != counts or sum(actual) != len(roster.entries):
            raise ValidationError(f'{roster.name}: los grupos deben contener {counts}; se encontró {actual}.')
        names = [normalizar(e[0]) for e in roster.entries]
        if any(not n for n in names) or len(names) != len(set(names)):
            raise ValidationError(f'{roster.name}: hay nombres vacíos o duplicados.')
    return result


def import_roster(state: State, roster: Roster, replace=False) -> None:
    existing = state.competitions.get(roster.name)
    previous = {normalizar(t.nombre_equipo): t for t in existing.teams + existing.reserve} if existing else {}
    previous_ids = {t.id_equipo: t for t in existing.teams + existing.reserve} if existing else {}
    cupos = existing.config.cupos_clasificados if existing else min(32, max(n for n in FASES if n <= len(roster.entries)))
    if cupos > len(roster.entries):
        raise ValidationError('La lista tiene menos equipos que los cupos configurados.')
    teams = []
    for name, group, status, team_id in roster.entries:
        old = previous_ids.get(team_id) or previous.get(normalizar(name))
        if team_id and team_id not in previous_ids:
            raise ValidationError('Se alteró un ID interno de equipo. Pega listas nuevas sin la columna oculta.')
        team = deepcopy(old) if old else Team(new_id(), name, roster.name)
        team.nombre_equipo, team.grupo = name, group
        team.estado, team.clasificado = TO_INTERNAL[status], status == 'Clasifica'
        teams.append(team)
    config = Config(roster.name, len(teams), roster.groups, roster.participants, cupos,
                    fase_actual='Grupos', torneo_iniciado=True,
                    equipos_por_grupo=', '.join(map(str, distribuir(len(teams), roster.groups))),
                    metodo_grupos='Listado importado', titulo=roster.title, fecha=roster.date)
    config.sistema = existing.config.sistema if existing else "Libre"
    candidate = Competition(config, teams)
    if existing:
        candidate.reserve = [deepcopy(t) for t in existing.reserve if t.id_equipo not in {team.id_equipo for team in teams}]
        order = {t.id_equipo:i for i,t in enumerate(existing.teams)}
        candidate.teams.sort(key=lambda t:order.get(t.id_equipo, len(order)))
        if {t.id_equipo:t.grupo for t in teams} == {t.id_equipo:t.grupo for t in existing.teams}:
            candidate.config.metodo_grupos = existing.config.metodo_grupos
    if existing and existing.matches and not replace:
        # Después de cerrar grupos solo se permiten nombres/participantes; el resto
        # requiere reiniciar eliminatorias desde la administración.
        old_roster = {t.id_equipo: (t.grupo, t.estado) for t in existing.teams}
        new_roster = {t.id_equipo: (t.grupo, t.estado) for t in teams}
        if old_roster != new_roster or roster.groups != existing.config.numero_grupos:
            raise ValidationError('Grupos ya está cerrado. Reinicia las eliminatorias como administrador para cambiar sus clasificados o equipos.')
        candidate.matches = deepcopy(existing.matches)
        candidate.config.fase_actual = existing.config.fase_actual
        candidate.config.campeon = existing.config.campeon
    if config.sistema == "Libre":
        from core.free_rounds import reconcile
        candidate.rounds = deepcopy(existing.rounds) if existing else {}
        reconcile(candidate)
    state.competitions[roster.name] = candidate


def group_rows(state: State) -> list[list]:
    rows = []
    for c in state.competitions.values():
        if not c.config.torneo_iniciado:
            continue
        rows.extend([['TORNEOS DE ROBÓTICA'], [c.config.titulo],
                     [f'Competencia: {c.config.competencia}'], [f'Fecha: {c.config.fecha}'],
                     [f'Participantes: {c.config.numero_participantes} | Grupos: {c.config.numero_grupos}'],
                     ['Nombre del equipo', 'Estado', 'id_equipo']])
        for i in range(c.config.numero_grupos):
            group = nombre_columna(i + 1)
            rows.append([f'Equipo {i+1}'])
            rows.extend([[f'• {t.nombre_equipo}', TO_PUBLIC[t.estado], t.id_equipo]
                         for t in c.teams if t.grupo == group])
            rows.append([])
    return rows or [['TORNEOS DE ROBÓTICA'], ['Pega aquí el listado completo, desde A1.']]


def phase_rows(state: State, phase: str) -> list[list]:
    rows = [['TORNEOS DE ROBÓTICA · ' + PHASE_SHEETS[phase]],
            ['N.º', 'Equipo', 'Estado', 'id_partido', 'id_equipo']]
    for c in state.competitions.values():
        if c.config.sistema == 'Libre':
            entries=c.rounds.get(phase,{})
            if entries:
                rows.append(['Competencia: '+c.config.competencia])
                for i,(tid,status) in enumerate(entries.items(),1):
                    rows.append([i,c.name(tid),TO_PUBLIC[status],f'free:{phase}:{tid}',tid])
            continue
        matches = partidos_fase(c, phase)
        if not matches:
            index = ORDEN_FASES.index(phase)
            previous = partidos_fase(c, ORDEN_FASES[index-1]) if index else []
            winners = [m for m in previous if m.ganador]
            if winners:
                rows.append(['Competencia: ' + c.config.competencia])
                for m in winners:
                    rows.append([(m.numero_partido+1)//2,c.name(m.ganador),'En espera','',m.ganador])
            continue
        rows.append(['Competencia: ' + c.config.competencia])
        for m in matches:
            for tid in (m.equipo_1, m.equipo_2):
                if not tid:
                    continue
                status = 'Pendiente' if not m.ganador else 'Clasifica' if m.ganador == tid else 'No clasifica'
                rows.append([m.numero_partido, c.name(tid), status, m.id_partido, tid])
    return rows


def stage_tables(state: State) -> dict:
    return {'Grupos': board_rows(state), **{tab: phase_rows(state, phase) for phase, tab in PHASE_SHEETS.items()}}


def apply_sheet_edits(state: State, tables: dict, strict=True) -> State:
    """Reconciliación de entradas editadas, sin tomar proyecciones viejas por cambios.

    Compara contra la proyección del estado persistido y aplica solo decisiones
    modificadas. Las fases vacías no se crean hasta completar la anterior.
    """
    updated = deepcopy(state)
    raw_groups = tables.get('Grupos', [])
    actions = {}
    is_board = bool(raw_groups and raw_groups[0] and raw_groups[0][0] == MARKER)
    if is_board:
        raw_groups, actions = parse_board(state, raw_groups)
    if raw_groups and raw_groups[0] and str(raw_groups[0][0]).startswith('TORNEOS DE ROBÓTICA') and normalized_rows(raw_groups) != normalized_rows(group_rows(state)):
        rosters = parse_rosters(raw_groups)
        present = {r.name for r in rosters}
        missing = {name for name,c in state.competitions.items() if c.config.torneo_iniciado} - present
        if missing:
            raise ValidationError('Falta el listado de una competencia existente. Usa Administración para reiniciarla; no borres bloques de Grupos.')
        for roster in rosters:
            before = deepcopy(updated.competitions.get(roster.name))
            import_roster(updated, roster)
            c = updated.competitions[roster.name]
            # No iniciar un torneo ya clasificado al realizar una lectura sin cambios.
            changed = before is None or {t.id_equipo:t.estado for t in before.teams} != {t.id_equipo:t.estado for t in c.teams}
            if changed and not c.matches and all(t.estado != "Pendiente" for t in c.teams) and sum(t.clasificado for t in c.teams) == c.config.cupos_clasificados:
                iniciar_eliminatorias(c)
    for name, quantities in actions.items():
        resize_groups(updated.competitions[name], *quantities)
    legacy = not raw_groups or not raw_groups[0] or not str(raw_groups[0][0]).startswith('TORNEOS DE ROBÓTICA')
    for phase, tab in PHASE_SHEETS.items():
        if legacy and not tables.get(tab):
            continue
        candidate = deepcopy(updated)
        try:
            _apply_phase_edits(candidate, state, tables, phase, tab)
        except ValidationError as error:
            if strict:
                raise
            issues = dict(getattr(updated, 'sync_issues', {}))
            issues[tab] = str(error)
            updated.sync_issues = issues
            updated.sync_error = ' | '.join(issues.values())
        else:
            updated = candidate
    validar_estado(updated)
    return updated


def _apply_phase_edits(updated, state, tables, phase, tab):
    for name,c in updated.competitions.items():
        if c.config.sistema != 'Libre':continue
        old=state.competitions[name].rounds.get(phase,{}) if name in state.competitions else {}
        found={}
        for row in tables.get(tab,[]):
            if len(row)<5 or row[4] not in old:continue
            tid=str(row[4])
            if str(row[3]) != f'free:{phase}:{tid}' or tid in found:
                raise ValidationError(f'{tab}: registro libre duplicado o ID modificado.')
            if row[2] not in STATES:raise ValidationError(f'{tab}: estado inválido.')
            found[tid]=TO_INTERNAL[row[2]]
        if set(found)!=set(old):raise ValidationError(f'{tab}: faltan equipos de la fase; usa los desplegables.')
        for tid,status in found.items():
            if status != old[tid] and tid in c.rounds.get(phase,{}):c.rounds[phase][tid]=status
        from core.free_rounds import reconcile
        reconcile(c)
    expected = {(str(row[3]), str(row[4])): row[2] for row in phase_rows(state,phase) if len(row) >= 5 and row[3] and row[3] != 'id_partido' and not str(row[3]).startswith('free:')}
    changed, all_rows, seen = {}, {}, set()
    for row in tables.get(tab, []):
        if len(row) < 4 or row[3] in ('', 'id_partido') or str(row[3]).startswith('free:'):
            continue
        if len(row) < 5 or not row[4]:
            raise ValidationError(f'{tab}: faltan IDs de un cruce. No cambies las columnas ocultas.')
        key = (str(row[3]), str(row[4]))
        if key in seen or key not in expected:
            raise ValidationError(f'{tab}: equipo/partido duplicado o desconocido.')
        seen.add(key)
        status = str(row[2] or 'Pendiente')
        if status not in STATES:
            raise ValidationError(f'{tab}: estado inválido.')
        all_rows.setdefault(key[0], {})[key[1]] = status
        if status != expected[key]:
            changed.setdefault(key[0], {})[key[1]] = status
    if expected and seen != set(expected):
        raise ValidationError(f'{tab}: no elimines participantes de una ronda. Selecciona su estado.')
    for mid, changes in changed.items():
        c = next((c for c in updated.competitions.values() if any(m.id_partido == mid for m in c.matches)), None)
        if c is None:
            raise ValidationError('El partido ya no existe.')
        m = next(m for m in c.matches if m.id_partido == mid)
        if m.ganador:
            raise ValidationError(f'{tab}, partido {m.numero_partido}: corrige resultados finalizados desde Administración/Eliminatorias y confirma sus efectos.')
        statuses = all_rows[mid]
        winners = [t for t,s in statuses.items() if s == 'Clasifica']
        losers = [t for t,s in statuses.items() if s == 'No clasifica']
        if len(winners)>1 or len(losers)>1:
            raise ValidationError(f'{tab}, partido {m.numero_partido}: solo puede clasificar un equipo.')
        winner = winners[0] if winners else next((t for t in (m.equipo_1,m.equipo_2) if t and t not in losers), '') if losers else ''
        if winner:
            actualizar_ganador(c, mid, winner)


def active_participants(c: Competition) -> list[dict]:
    if c.config.sistema == 'Libre':
        from core.free_rounds import active
        current=active(c)
        return [{'Equipo':t.nombre_equipo,'Grupo de origen':t.grupo,'Fase actual':current[t.id_equipo]} for t in c.teams if t.id_equipo in current]
    if c.config.campeon:
        ids = {c.config.campeon}
    elif c.matches:
        current = partidos_fase(c, c.config.fase_actual)
        ids = {tid for m in current for tid in (m.equipo_1,m.equipo_2) if tid and (not m.ganador or tid==m.ganador)}
    else:
        ids = {t.id_equipo for t in c.teams if t.estado != 'Eliminado'}
    return [{'Equipo': t.nombre_equipo, 'Grupo de origen': t.grupo,
             'Fase actual': 'Campeón' if c.config.campeon else c.config.fase_actual}
            for t in c.teams if t.id_equipo in ids]


def history_rows(c: Competition) -> list[dict]:
    rows = [{'Fase':'Grupos','Partido':'','Equipo':t.nombre_equipo,'Grupo':t.grupo,
             'Resultado': TO_PUBLIC[t.estado]} for t in c.teams]
    if c.config.sistema == 'Libre':
        for phase,entries in c.rounds.items():
            for tid,status in entries.items():
                rows.append({'Fase':phase,'Partido':'','Equipo':c.name(tid),'Grupo':next(t.grupo for t in c.teams if t.id_equipo==tid),'Resultado':'Campeón' if tid==c.config.campeon and phase=='Final' else TO_PUBLIC[status]})
        return rows
    for phase in ORDEN_FASES:
        for m in partidos_fase(c,phase):
            for tid in (m.equipo_1,m.equipo_2):
                if tid:
                    rows.append({'Fase':phase,'Partido':str(m.numero_partido),'Equipo':c.name(tid),
                                 'Grupo':next(t.grupo for t in c.teams if t.id_equipo==tid),
                                 'Resultado':'Pendiente' if not m.ganador else 'Campeón' if phase=='Final' and m.ganador==tid else 'Clasifica' if m.ganador==tid else 'No clasifica'})
    return rows
