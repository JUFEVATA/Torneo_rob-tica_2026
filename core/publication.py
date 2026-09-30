"""Presentación pública y papelera, independientes de los resultados deportivos."""
from core.eliminatorias import ORDEN_FASES, partidos_fase
from core.models import ValidationError, new_id

PUBLIC_PAGES = ["Inicio", "Fases", "Podio"]
STAGES = ["Inscripción", "Grupos", *ORDEN_FASES, "Finalizado"]
LABELS = {"Treintaidosavos": "32 avos", "Dieciseisavos": "16 avos", "Octavos": "8vos",
          "Cuartos": "4tos", "Semifinal": "Semifinal", "Final": "Final", "Finalizado": "Finalizado",
          "Grupos": "Grupos", "Inscripción": "Inscripción"}


def public_name(state):
    if state.public_competition in state.competitions:
        return state.public_competition
    return next((name for name, c in state.competitions.items() if c.config.torneo_iniciado),
                next(iter(state.competitions), None))


def shown_stage(c):
    return c.config.etapa_publica or c.config.fase_actual


def publish(state, name, stage=""):
    if name not in state.competitions or stage and stage not in STAGES:
        raise ValidationError("Competencia o etapa de publicación inválida.")
    state.public_competition = name
    state.competitions[name].config.etapa_publica = stage


def podium(c):
    manual_ids = {c.config.puesto_1, c.config.puesto_2, c.config.puesto_3} - {""}
    first = c.config.puesto_1 or (c.config.campeon if c.config.campeon not in manual_ids else "")
    second = c.config.puesto_2
    if not second and c.config.sistema != "Libre" and c.config.campeon:
        final = partidos_fase(c, "Final")[0]
        runner_up = next(t for t in (final.equipo_1, final.equipo_2) if t != c.config.campeon)
        second = runner_up if runner_up not in manual_ids else ""
    result = {1: first, 2: second, 3: c.config.puesto_3}
    # Una decisión manual puede reasignar los puestos automáticos.
    used = set()
    for position, tid in result.items():
        if tid in used:
            result[position] = ""
        elif tid:
            used.add(tid)
    return result


def save_podium(c, first, second, third):
    ids = [tid for tid in (first, second, third) if tid]
    if len(ids) != len(set(ids)):
        raise ValidationError("Un equipo no puede ocupar dos puestos del podio.")
    if not set(ids) <= {t.id_equipo for t in c.teams}:
        raise ValidationError("Selecciona equipos inscritos en esta competencia.")
    c.config.puesto_1, c.config.puesto_2, c.config.puesto_3 = first, second, third


def archive(state, name):
    if name not in state.competitions:
        raise ValidationError("La competencia ya no existe.")
    state.archived[new_id()] = state.competitions.pop(name)
    if state.public_competition == name:
        state.public_competition = ""


def restore(state, archive_id):
    if archive_id not in state.archived:
        raise ValidationError("No se encontró la competencia en la papelera.")
    c = state.archived[archive_id]
    if c.config.competencia in state.competitions:
        raise ValidationError("Ya existe una competencia con ese nombre. Renómbrala antes de restaurar.")
    state.competitions[c.config.competencia] = state.archived.pop(archive_id)


def validate_publication(state):
    if state.public_competition and state.public_competition not in state.competitions:
        raise ValidationError("La competencia pública no existe.")
    for c in state.competitions.values():
        if c.config.etapa_publica and c.config.etapa_publica not in STAGES:
            raise ValidationError("Etapa pública inválida.")
        save_podium(c, c.config.puesto_1, c.config.puesto_2, c.config.puesto_3)
