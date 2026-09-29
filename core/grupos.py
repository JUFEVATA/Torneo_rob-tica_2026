"""Distribución circular: los sobrantes siempre corresponden a A, B, C…"""
from random import SystemRandom

from core.models import Team, ValidationError


def nombre_columna(numero: int) -> str:
    if type(numero) is not int or numero < 1:
        raise ValidationError("El índice de columna debe ser un entero positivo.")
    nombre = ""
    while numero:
        numero, resto = divmod(numero - 1, 26)
        nombre = chr(65 + resto) + nombre
    return nombre


def distribuir(numero_equipos: int, numero_grupos: int) -> list[int]:
    if any(type(n) is not int or n <= 0 for n in (numero_equipos, numero_grupos)):
        raise ValidationError("Equipos y grupos deben ser enteros mayores que cero.")
    if numero_grupos > numero_equipos:
        raise ValidationError("No puede haber más grupos que equipos.")
    base, sobrantes = divmod(numero_equipos, numero_grupos)
    return [base + (i < sobrantes) for i in range(numero_grupos)]


def generar_grupos(equipos: list[Team], numero_grupos: int, sorteo: bool = False) -> list[Team]:
    distribuir(len(equipos), numero_grupos)
    orden = list(equipos)
    if sorteo:
        SystemRandom().shuffle(orden)
    for i, equipo in enumerate(orden):
        equipo.grupo = nombre_columna(i % numero_grupos + 1)
    # Se conserva el orden de inscripción; solo cambia el grupo persistido.
    return equipos
