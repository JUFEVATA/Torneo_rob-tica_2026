"""Repositorio local para demostración, con la misma interfaz transaccional."""
from copy import deepcopy
from pathlib import Path
from threading import RLock
import json
import os
import tempfile

from core.models import ConflictError, State
from core.tournament import validar_estado
from services.serialization import fingerprint

_LOCK = RLock()


class LocalRepository:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read(self) -> tuple[State, str]:
        with _LOCK:
            data = json.loads(self.path.read_text()) if self.path.exists() else State().to_dict()
            state = State.from_dict(data)
            validar_estado(state)
            return state, fingerprint(data)

    def recovery_options(self):
        data = json.loads(self.path.read_text()) if self.path.exists() else State().to_dict()
        return list(data["competitions"]), fingerprint(data)

    def recover(self, revision, name, action):
        from core.recovery import force_operation
        from core.models import Config, Competition, new_id
        from datetime import datetime, timezone
        with _LOCK:
            data = json.loads(self.path.read_text())
            if fingerprint(data) != revision:
                raise ConflictError("Los datos cambiaron. Actualiza antes de recuperar.")
            try:
                state = State.from_dict(data)
            except (TypeError, KeyError):
                cleaned = deepcopy(data)
                cleaned["competitions"].pop(name, None)
                if cleaned.get("public_competition") == name: cleaned["public_competition"] = ""
                state = State.from_dict(cleaned)
                if action != "Eliminar": state.competitions[name] = Competition(Config(name, 32, 1, cupos_clasificados=16, sistema="Libre"))
            if name in state.competitions: force_operation(state, name, action)
            validar_estado(state)
            snapshot = deepcopy(data)
            snapshot.pop('recovery_backups', None)
            state.recovery_backups[new_id()] = {"competencia": name, "accion": action, "fecha": datetime.now(timezone.utc).isoformat(), "datos": snapshot}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".recovery-")
            try:
                with os.fdopen(fd, "w") as out:
                    json.dump(state.to_dict(), out, ensure_ascii=False, indent=2)
                    out.flush(); os.fsync(out.fileno())
                os.replace(temporary, self.path)
            finally:
                if os.path.exists(temporary): os.unlink(temporary)
            return self.read()

    def transact(self, revision: str, operation) -> tuple[State, str]:
        with _LOCK:
            state, actual = self.read()
            if revision != actual:
                raise ConflictError("Los datos cambiaron en otra sesión. Actualiza y vuelve a intentar.")
            updated = deepcopy(state)
            operation(updated)
            validar_estado(updated)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".torneo-", suffix=".json")
            try:
                with os.fdopen(fd, "w") as out:
                    json.dump(updated.to_dict(), out, ensure_ascii=False, indent=2)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(temporary, self.path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            return self.read()
