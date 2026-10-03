"""Recuperación explícita: respalda entradas crudas y omite borradores del torneo elegido."""
from copy import deepcopy
from datetime import datetime, timezone
from core.models import Config, ValidationError, new_id
from core.publication import archive


def force_operation(state, name, action):
    if name not in state.competitions:
        raise ValidationError("La competencia no existe.")
    if action == "Eliminar":
        archive(state, name)
        return
    if action not in ("Reiniciar resultados", "Reiniciar competencia"):
        raise ValidationError("Acción de recuperación desconocida.")
    c = state.competitions[name]
    if action == "Reiniciar competencia":
        old = c.config
        total = old.numero_equipos if type(old.numero_equipos) is int and 2 <= old.numero_equipos <= 4096 else 32
        groups = old.numero_grupos if type(old.numero_grupos) is int and 1 <= old.numero_grupos <= total else 1
        cap = old.cupos_clasificados if old.cupos_clasificados in (2, 4, 8, 16, 32, 64) and old.cupos_clasificados <= total else min(16, max(n for n in (2, 4, 8, 16, 32, 64) if n <= total))
        c.config = Config(name, total, groups, cupos_clasificados=cap, sistema=old.sistema if old.sistema in ("Libre", "Enfrentamientos", "Tiempos") else "Libre", titulo=old.titulo)
        c.teams.clear(); c.reserve.clear()
    else:
        for t in c.teams:
            t.estado, t.clasificado = "Pendiente", False
        c.config.puesto_1 = c.config.puesto_2 = c.config.puesto_3 = c.config.campeon = ""
        c.config.etapa_publica = ""
    c.matches.clear(); c.rounds.clear(); c.timing.clear(); c.closed_phases.clear()
    if c.config.sistema == "Libre":
        from core.free_rounds import reconcile
    elif c.config.sistema == "Tiempos":
        from core.line_racing import reconcile
    else:
        from core.eliminatorias import reconciliar as reconcile
    reconcile(c)


def replace_competition_rows(raw, projected, name, tab):
    if tab == "Podio":
        return [projected[0]] + [r for r in raw[1:] if r and r[0] != name] + [r for r in projected[1:] if r and r[0] == name]
    header = 2 if tab == "Grupos" else 3 if tab.startswith("SL ") else 2
    def blocks(rows):
        starts = [i for i, row in enumerate(rows) if row and str(row[0]).startswith("Competencia: ")]
        return [(str(rows[start][0])[13:], rows[start:starts[j+1] if j+1 < len(starts) else len(rows)]) for j, start in enumerate(starts)]
    return projected[:header] + [r for n, block in blocks(raw) if n != name for r in block] + [r for n, block in blocks(projected) if n == name for r in block]


def recover_tables(original, name, action):
    from services.serialization import decode
    from core.sheet_flow import stage_tables, apply_sheet_edits
    from core.tournament import validar_estado
    try:
        state = decode(original, validate=False)
    except (ValidationError, ValueError, TypeError, KeyError):
        # Campos ilegibles del torneo elegido no impiden retirarlo. Se guardan íntegros.
        cleaned = deepcopy(original)
        for tab, rows in cleaned.items():
            if not rows or "competencia" not in rows[0] or tab == "Podio": continue
            col = rows[0].index("competencia")
            cleaned[tab] = [rows[0]] + [r for r in rows[1:] if len(r) <= col or r[col] != name]
        state = decode(cleaned, validate=False)
        if action != "Eliminar":
            from core.models import Competition
            state.competitions[name] = Competition(Config(name, 32, 1, cupos_clasificados=16, sistema="Libre"))
        elif state.public_competition == name:
            state.public_competition = ""
    if name in state.competitions:
        force_operation(state, name, action)
    elif action != "Eliminar":
        raise ValidationError("No se pudo identificar la competencia a reiniciar.")
    validar_estado(state)
    projected = stage_tables(state)
    safe_inputs = deepcopy(original)
    for tab, rows in projected.items():
        safe_inputs[tab] = replace_competition_rows(original.get(tab, []), rows, name, tab)
    state = apply_sheet_edits(state, safe_inputs, strict=False)
    state.recovery_backups[new_id()] = {"competencia": name, "accion": action, "fecha": datetime.now(timezone.utc).isoformat(), "hojas": deepcopy({tab: rows for tab, rows in original.items() if tab != "Recuperaciones"})}
    return state, safe_inputs
