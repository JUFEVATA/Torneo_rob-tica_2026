"""Bracket determinista con invalidación únicamente de las ramas afectadas."""
from core.models import Competition, Match, ValidationError, new_id

FASES = {64: "Treintaidosavos", 32: "Dieciseisavos", 16: "Octavos",
         8: "Cuartos", 4: "Semifinal", 2: "Final"}
ORDEN_FASES = list(FASES.values())


def fase_para(cantidad: int) -> str:
    if cantidad not in FASES:
        raise ValidationError("Los cupos deben ser 2, 4, 8, 16, 32 o 64. No se utilizan pases libres.")
    return FASES[cantidad]


def partidos_fase(c: Competition, fase: str) -> list[Match]:
    return sorted((m for m in c.matches if m.fase == fase), key=lambda m: m.numero_partido)


def crear_ronda(competencia: str, equipos: list[str]) -> list[Match]:
    fase = fase_para(len(equipos))
    if len(set(equipos)) != len(equipos) or not all(equipos):
        raise ValidationError("Cada equipo debe ocupar un único lugar en la ronda.")
    return [Match(new_id(), competencia, fase, i // 2 + 1, equipos[i], equipos[i + 1])
            for i in range(0, len(equipos), 2)]


def reconciliar(c: Competition) -> None:
    """Propaga ganadores, crea rondas completas y limpia descendientes incompatibles.

    Una ronda existente mantiene sus IDs. Si cambia cualquiera de sus participantes,
    se borra su resultado aunque el ganador antiguo todavía sea participante.
    Los partidos de las otras ramas permanecen intactos.
    """
    c.config.campeon = ""
    if not c.matches:
        c.config.fase_actual = "Grupos" if c.config.torneo_iniciado else "Inscripción"
        return
    primera = min(ORDEN_FASES.index(m.fase) for m in c.matches)
    for index in range(primera, len(ORDEN_FASES) - 1):
        anterior = partidos_fase(c, ORDEN_FASES[index])
        siguiente_fase = ORDEN_FASES[index + 1]
        siguiente = partidos_fase(c, siguiente_fase)
        completos = bool(anterior) and all(m.ganador for m in anterior)
        if not siguiente and completos:
            c.matches.extend(crear_ronda(c.config.competencia, [m.ganador for m in anterior]))
            siguiente = partidos_fase(c, siguiente_fase)
        for i, partido in enumerate(siguiente):
            nuevos = (anterior[2 * i].ganador, anterior[2 * i + 1].ganador)
            if (partido.equipo_1, partido.equipo_2) != nuevos:
                partido.equipo_1, partido.equipo_2 = nuevos
                partido.ganador = ""
            partido.estado = ("Finalizado" if partido.ganador else
                              "Pendiente" if all(nuevos) else "Por definir")
    final = partidos_fase(c, "Final")
    if final and final[0].ganador:
        c.config.campeon = final[0].ganador
        c.config.fase_actual = "Finalizado"
    else:
        c.config.fase_actual = next(f for f in ORDEN_FASES
                                   if any(not m.ganador for m in partidos_fase(c, f)))


def actualizar_ganador(c: Competition, id_partido: str, ganador: str, confirmar: bool = False) -> None:
    partido = next((m for m in c.matches if m.id_partido == id_partido), None)
    if partido is None:
        raise ValidationError("El partido no existe.")
    if ganador and (not partido.equipo_1 or not partido.equipo_2 or
                    ganador not in (partido.equipo_1, partido.equipo_2)):
        raise ValidationError("El ganador debe ser uno de los dos participantes definidos.")
    if partido.ganador and partido.ganador != ganador and not confirmar:
        raise ValidationError("Este cambio afecta fases posteriores. Confirma la corrección.")
    # También evita jugar ramas de una ronda mientras la anterior está pendiente.
    index = ORDEN_FASES.index(partido.fase)
    if ganador and any(not m.ganador for m in c.matches if ORDEN_FASES.index(m.fase) < index):
        raise ValidationError("Primero deben terminar todos los partidos de la fase anterior.")
    partido.ganador = ganador
    partido.estado = "Finalizado" if ganador else "Pendiente"
    reconciliar(c)


def reseed(c):
    """Corrige grupos conservando las parejas y los resultados no afectados."""
    first = fase_para(c.config.cupos_clasificados)
    qualifying = {t.id_equipo for t in c.teams if t.clasificado}
    matches = partidos_fase(c, first)
    retained = {tid for m in matches for tid in (m.equipo_1, m.equipo_2) if tid in qualifying}
    added = iter(t.id_equipo for t in c.teams if t.clasificado and t.id_equipo not in retained)
    for m in matches:
        pair = tuple(tid if tid in qualifying else next(added, "") for tid in (m.equipo_1, m.equipo_2))
        if pair != (m.equipo_1, m.equipo_2):
            m.equipo_1, m.equipo_2 = pair
            m.ganador = ""
        m.estado = "Finalizado" if m.ganador else "Pendiente" if all(pair) else "Por definir"
    reconciliar(c)
