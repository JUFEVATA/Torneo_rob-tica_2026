"""Reglas de negocio. Las mutaciones se ejecutan dentro de una transacción del repositorio."""
from collections import Counter
from random import SystemRandom
import unicodedata

from core.eliminatorias import (FASES, ORDEN_FASES, actualizar_ganador, crear_ronda,
                               fase_para, partidos_fase, reconciliar)
from core.grupos import distribuir, generar_grupos, nombre_columna
from core.models import Competition, Config, State, Team, ValidationError, new_id


def normalizar(nombre: str) -> str:
    return unicodedata.normalize("NFKC", " ".join(nombre.split())).casefold()


def validar_config(config: Config) -> None:
    if not config.competencia.strip() or len(config.competencia) > 100:
        raise ValidationError("La competencia debe tener entre 1 y 100 caracteres.")
    if config.sistema not in ("Libre", "Enfrentamientos", "Tiempos"):
        raise ValidationError("Sistema de clasificación desconocido.")
    distribuir(config.numero_equipos, config.numero_grupos)
    fase_para(config.cupos_clasificados)
    if config.cupos_clasificados > config.numero_equipos:
        raise ValidationError("Los cupos no pueden superar el total de equipos; se requieren al menos 2 equipos para eliminatorias.")
    if type(config.numero_participantes) is not int or config.numero_participantes < 0:
        raise ValidationError("El total de participantes no puede ser negativo.")
    if config.regla_fallos not in ("Acumulados", "Por fase"):
        raise ValidationError("Regla de fallos desconocida.")


def crear_competencia(state: State, config: Config) -> None:
    config.competencia = " ".join(config.competencia.split())
    validar_config(config)
    if any(normalizar(n) == normalizar(config.competencia) for n in state.competitions):
        raise ValidationError("Ya existe una competencia con ese nombre.")
    state.competitions[config.competencia] = Competition(config)


def configurar(c: Competition, total: int, grupos: int, participantes: int, cupos: int) -> None:
    if c.config.torneo_iniciado:
        raise ValidationError("Reinicia la fase de grupos para cambiar la estructura.")
    if total < len(c.teams):
        raise ValidationError("El total esperado no puede ser menor que los equipos registrados.")
    c.config.numero_equipos, c.config.numero_grupos = total, grupos
    c.config.numero_participantes, c.config.cupos_clasificados = participantes, cupos
    validar_config(c.config)


def agregar_equipos(c: Competition, nombres: list[str], participantes: list[int] | None = None) -> None:
    if c.config.torneo_iniciado:
        raise ValidationError("Reinicia los grupos antes de agregar o eliminar equipos.")
    nombres = [" ".join(n.split()) for n in nombres]
    if not nombres or any(not n or len(n) > 100 for n in nombres):
        raise ValidationError("Escribe nombres de 1 a 100 caracteres.")
    todos = [normalizar(t.nombre_equipo) for t in c.teams] + [normalizar(n) for n in nombres]
    if len(todos) != len(set(todos)):
        raise ValidationError("Hay nombres duplicados (se ignoran mayúsculas y espacios repetidos).")
    if len(c.teams) + len(nombres) > c.config.numero_equipos:
        raise ValidationError("La lista supera la cantidad de equipos configurada.")
    participantes = participantes if participantes is not None else [0] * len(nombres)
    if len(participantes) != len(nombres) or any(type(n) is not int or n < 0 for n in participantes):
        raise ValidationError("Los participantes deben ser enteros no negativos, uno por equipo.")
    c.teams.extend(Team(new_id(), n, c.config.competencia, numero_participantes=p)
                   for n, p in zip(nombres, participantes))


def editar_equipo(c: Competition, team_id: str, nombre: str, participantes: int) -> None:
    equipo = next((t for t in c.teams if t.id_equipo == team_id), None)
    if equipo is None:
        raise ValidationError("El equipo ya no existe.")
    nombre = " ".join(nombre.split())
    if not nombre or len(nombre) > 100:
        raise ValidationError("El nombre debe tener entre 1 y 100 caracteres.")
    if any(t.id_equipo != team_id and normalizar(t.nombre_equipo) == normalizar(nombre) for t in c.teams):
        raise ValidationError("Ya existe otro equipo con ese nombre.")
    if type(participantes) is not int or participantes < 0:
        raise ValidationError("Los participantes deben ser enteros no negativos.")
    equipo.nombre_equipo, equipo.numero_participantes = nombre, participantes
    if c.config.sistema == "Tiempos" and participantes > 2:
        raise ValidationError("Seguidor de línea admite máximo dos integrantes por equipo.")


def eliminar_equipo(c: Competition, team_id: str) -> None:
    if c.config.torneo_iniciado:
        raise ValidationError("Reinicia los grupos antes de eliminar equipos.")
    c.teams = [t for t in c.teams if t.id_equipo != team_id]


def completar_genericos(c: Competition) -> None:
    nombres, existentes = [], {normalizar(t.nombre_equipo) for t in c.teams}
    i = 1
    while len(c.teams) + len(nombres) < c.config.numero_equipos:
        nombre = f"Equipo {i}"
        if normalizar(nombre) not in existentes:
            nombres.append(nombre)
        i += 1
    if nombres:
        agregar_equipos(c, nombres)


def iniciar_grupos(c: Competition, sorteo: bool = False, genericos: bool = False) -> None:
    if c.config.torneo_iniciado:
        raise ValidationError("Los grupos ya están guardados. Reinicia la fase antes de regenerarlos.")
    if genericos:
        completar_genericos(c)
    if len(c.teams) != c.config.numero_equipos:
        raise ValidationError("Registra todos los equipos o activa los nombres genéricos.")
    generar_grupos(c.teams, c.config.numero_grupos, sorteo)
    c.config.equipos_por_grupo = ", ".join(map(str, distribuir(len(c.teams), c.config.numero_grupos)))
    c.config.torneo_iniciado = True
    c.config.fase_actual = "Grupos"
    c.config.metodo_grupos = "Sorteo aleatorio" if sorteo else "Orden original"
    if c.config.sistema == "Tiempos":
        from core.line_racing import reconcile
        reconcile(c)


def clasificar(c: Competition, team_id: str, estado: str) -> None:
    if c.config.sistema == "Libre":
        from core.free_rounds import classify
        classify(c,"Grupos",team_id,estado)
        return
    if c.config.sistema == "Tiempos":
        raise ValidationError("Esta competencia clasifica por tiempos; usa Registro de tiempos.")
    if not c.config.torneo_iniciado:
        raise ValidationError("Primero inicia la competencia.")
    if estado not in ("Clasificado", "Eliminado", "Pendiente"):
        raise ValidationError("Estado de clasificación inválido.")
    equipo = next((t for t in c.teams if t.id_equipo == team_id), None)
    if equipo is None:
        raise ValidationError("El equipo no existe.")
    if estado == "Clasificado" and not equipo.clasificado:
        if sum(t.clasificado for t in c.teams) >= c.config.cupos_clasificados:
            raise ValidationError("Ya se completaron todos los cupos de clasificación.")
    equipo.estado, equipo.clasificado = estado, estado == "Clasificado"
    if c.matches:
        from core.eliminatorias import reseed
        reseed(c)


def iniciar_eliminatorias(c: Competition, sorteo: bool = False) -> None:
    if c.config.sistema == "Tiempos":
        raise ValidationError("Las fases de seguidor de línea avanzan al cerrar los tiempos.")
    if c.config.sistema == "Libre":
        from core.free_rounds import reconcile
        reconcile(c)
        return
    if c.matches:
        raise ValidationError("Las eliminatorias ya se generaron.")
    if not c.config.torneo_iniciado:
        raise ValidationError("Primero genera los grupos.")
    equipos = [t.id_equipo for t in c.teams if t.clasificado]
    if len(equipos) != c.config.cupos_clasificados:
        raise ValidationError("Completa exactamente la cantidad requerida de clasificados.")
    if sorteo:
        SystemRandom().shuffle(equipos)
    c.matches = crear_ronda(c.config.competencia, equipos)
    reconciliar(c)


def reiniciar(c: Competition, alcance: str, confirmar: bool = False) -> None:
    if not confirmar:
        raise ValidationError("El reinicio requiere confirmación.")
    c.config.puesto_1 = c.config.puesto_2 = c.config.puesto_3 = ""
    c.config.etapa_publica = ""
    if c.config.sistema == "Tiempos":
        from core.line_racing import reset
        reset(c, alcance)
        return
    if c.config.sistema == "Libre":
        from core.free_rounds import reset
        reset(c,alcance)
        return
    if alcance == "Competencia completa":
        c.teams.clear()
        c.reserve.clear()
        c.matches.clear()
        c.config.torneo_iniciado = False
    elif alcance == "Eliminatorias":
        c.matches.clear()
    elif alcance == "Fase actual":
        if c.matches:
            fase = "Final" if c.config.campeon else c.config.fase_actual
            index = ORDEN_FASES.index(fase)
            c.matches = [m for m in c.matches if ORDEN_FASES.index(m.fase) <= index]
            for m in partidos_fase(c, fase):
                m.ganador, m.estado = "", "Pendiente"
        else:
            c.config.torneo_iniciado = False
    else:
        raise ValidationError("Selecciona un alcance de reinicio válido.")
    if not c.config.torneo_iniciado:
        c.config.equipos_por_grupo = ""
        for t in c.teams:
            t.grupo, t.clasificado, t.estado = "", False, "Pendiente"
    reconciliar(c)


def validar_estado(state: State) -> None:
    """Rechaza datos manuales inconsistentes antes de mostrarlos o sobrescribirlos."""
    from core.publication import validate_publication
    validate_publication(state)
    ids, match_ids, nombres_comp = set(), set(), set()
    for nombre, c in state.competitions.items():
        validar_config(c.config)
        if nombre != c.config.competencia or normalizar(nombre) in nombres_comp:
            raise ValidationError("Identidad de competencia inválida o duplicada.")
        nombres_comp.add(normalizar(nombre))
        if len(c.teams) > c.config.numero_equipos:
            raise ValidationError(f"{nombre}: hay más equipos que el total configurado.")
        nombres, team_ids = set(), {t.id_equipo for t in c.teams}
        for t in c.teams:
            if not t.id_equipo or t.id_equipo in ids or t.competencia != nombre:
                raise ValidationError("ID de equipo duplicado o competencia incorrecta.")
            ids.add(t.id_equipo)
            n = normalizar(t.nombre_equipo)
            if not n or len(t.nombre_equipo) > 100 or n in nombres:
                raise ValidationError(f"{nombre}: nombres de equipos vacíos o duplicados.")
            nombres.add(n)
            if type(t.numero_participantes) is not int or t.numero_participantes < 0:
                raise ValidationError("Participantes inválidos en Equipos.")
            if t.estado not in ("Pendiente", "Clasificado", "Eliminado") or t.clasificado != (t.estado == "Clasificado"):
                raise ValidationError("En Equipos, clasificado y estado deben coincidir.")
        for t in c.reserve:
            if not t.id_equipo or t.id_equipo in ids or t.competencia != nombre:
                raise ValidationError("ID de reserva duplicado o competencia incorrecta.")
            ids.add(t.id_equipo)
            n = normalizar(t.nombre_equipo)
            if not n or len(t.nombre_equipo) > 100 or n in nombres:
                raise ValidationError("Nombre de reserva vacío o duplicado.")
            nombres.add(n)
            if t.grupo or t.estado != 'Pendiente' or t.clasificado:
                raise ValidationError("Un equipo en reserva no puede tener grupo ni clasificación.")
            if type(t.numero_participantes) is not int or t.numero_participantes < 0:
                raise ValidationError("Participantes inválidos en Reserva.")
        if sum(t.clasificado for t in c.teams) > c.config.cupos_clasificados:
            raise ValidationError("Hay más clasificados que cupos.")
        if c.config.torneo_iniciado:
            expected = dict(zip((nombre_columna(i + 1) for i in range(c.config.numero_grupos)),
                                distribuir(c.config.numero_equipos, c.config.numero_grupos)))
            if Counter(t.grupo for t in c.teams) != expected:
                raise ValidationError(f"{nombre}: los grupos no coinciden con la distribución configurada.")
            if c.config.equipos_por_grupo != ", ".join(map(str, expected.values())):
                raise ValidationError("equipos_por_grupo no coincide con la distribución guardada.")
        elif any(t.grupo or t.estado != "Pendiente" for t in c.teams) or c.matches:
            raise ValidationError("Hay grupos o partidos en un torneo no iniciado.")
        if c.config.sistema == "Tiempos":
            from core.line_racing import validate
            validate(c)
            continue
        if c.config.sistema == "Libre":
            from core.free_rounds import validate
            validate(c)
            continue
        for m in c.matches:
            if not m.id_partido or m.id_partido in match_ids or m.competencia != nombre or m.fase not in ORDEN_FASES:
                raise ValidationError("Partido duplicado o fase/competencia inválida.")
            match_ids.add(m.id_partido)
            if any(t and t not in team_ids for t in (m.equipo_1, m.equipo_2)):
                raise ValidationError("Un partido hace referencia a un equipo inexistente.")
            if m.equipo_1 and m.equipo_1 == m.equipo_2:
                raise ValidationError("Un equipo no puede enfrentarse a sí mismo.")
            if m.ganador and (not m.equipo_1 or not m.equipo_2 or m.ganador not in (m.equipo_1, m.equipo_2)):
                raise ValidationError("Ganador inválido en Partidos.")
            expected_status = "Finalizado" if m.ganador else "Pendiente" if m.equipo_1 and m.equipo_2 else "Por definir"
            if m.estado != expected_status:
                raise ValidationError("Estado y ganador del partido no coinciden.")
        if c.matches:
            fases = [f for f in ORDEN_FASES if partidos_fase(c, f)]
            first_index = ORDEN_FASES.index(fase_para(c.config.cupos_clasificados))
            if fases != ORDEN_FASES[first_index:first_index + len(fases)]:
                raise ValidationError("Las rondas deben ser consecutivas desde los cupos configurados.")
            for index, f in enumerate(fases):
                ronda = partidos_fase(c, f)
                cantidad = next(n for n, fase in FASES.items() if fase == f)
                if [m.numero_partido for m in ronda] != list(range(1, cantidad // 2 + 1)):
                    raise ValidationError("Numeración o cantidad de partidos incorrecta.")
                usados = [t for m in ronda for t in (m.equipo_1, m.equipo_2) if t]
                if len(usados) != len(set(usados)):
                    raise ValidationError("Un equipo aparece dos veces en una ronda.")
                if index == 0:
                    if set(usados) != {t.id_equipo for t in c.teams if t.clasificado} or len(usados) > cantidad:
                        raise ValidationError("La primera ronda no coincide con los clasificados.")
                else:
                    anterior = partidos_fase(c, fases[index - 1])
                    for i, m in enumerate(ronda):
                        if (m.equipo_1, m.equipo_2) != (anterior[2*i].ganador, anterior[2*i+1].ganador):
                            raise ValidationError("Los cruces no coinciden con los ganadores anteriores. Corrige desde la app.")
        final = partidos_fase(c, "Final")
        campeon = final[0].ganador if final else ""
        if c.config.campeon != campeon:
            raise ValidationError("El campeón guardado no coincide con la final.")
        if c.matches:
            pending = [f for f in ORDEN_FASES if any(not m.ganador for m in partidos_fase(c, f))]
            if not campeon and not pending:
                raise ValidationError("Falta generar la ronda siguiente. Registra los ganadores desde la aplicación.")
            actual = "Finalizado" if campeon else pending[0]
        else:
            actual = "Grupos" if c.config.torneo_iniciado else "Inscripción"
        if c.config.fase_actual != actual:
            raise ValidationError("fase_actual es un campo calculado. Restaura su valor antes de continuar.")
