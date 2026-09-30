"""Hoja visible del podio; nombres editables con identidades estables."""
from core.models import ValidationError
from core.publication import podium, save_podium

PODIUM_HEADER = ["Competencia", "Puesto", "Equipo", "id_equipo"]
UNDEFINED = "Por definir"


def podium_rows(state):
    rows = [list(PODIUM_HEADER)]
    for name, c in state.competitions.items():
        for position, tid in podium(c).items():
            rows.append([name, position, c.name(tid) if tid else UNDEFINED, tid])
    return rows


def apply_podium_edits(updated, previous, rows):
    if not rows or rows == [PODIUM_HEADER]:
        return  # hoja recién creada: se completa con los puestos guardados
    if rows[0] != PODIUM_HEADER:
        raise ValidationError("Podio: conserva los encabezados de la hoja.")
    expected = {(row[0], row[1]): row for row in podium_rows(previous)[1:]}
    seen, changes = set(), {}
    for row in rows[1:]:
        if not any(str(value).strip() for value in row):
            continue
        row = list(row) + [""] * max(0, 4-len(row))
        if isinstance(row[1], bool):
            raise ValidationError("Podio: puesto inválido.")
        try:
            position = int(str(row[1]))
        except (ValueError, TypeError):
            raise ValidationError("Podio: el puesto debe ser 1, 2 o 3.") from None
        key = str(row[0]), position
        if key not in expected or key in seen or str(row[3]) != expected[key][3]:
            raise ValidationError("Podio: registro duplicado o identidad modificada. Usa el desplegable de Equipo.")
        seen.add(key)
        name = str(row[2]).strip()
        if name == expected[key][2]:
            continue
        c = updated.competitions[key[0]]
        # Un nombre puede haber sido actualizado en Grupos en la misma lectura.
        names = {t.nombre_equipo: t.id_equipo for t in previous.competitions[key[0]].teams}
        names.update({t.nombre_equipo: t.id_equipo for t in c.teams})
        if name in ("", UNDEFINED):
            tid = ""
        elif name in names:
            tid = names[name]
        else:
            raise ValidationError(f"Podio: selecciona un equipo inscrito en {key[0]}.")
        changes.setdefault(key[0], {})[position] = tid
    if seen != set(expected):
        raise ValidationError("Podio: faltan puestos. No borres filas; selecciona Por definir.")
    for name, choices in changes.items():
        c = updated.competitions[name]
        positions = [choices.get(pos, getattr(c.config, f"puesto_{pos}")) for pos in (1, 2, 3)]
        save_podium(c, *positions)
