"""Google Sheets = fuente persistente. Lecturas por lote y commits atómicos.

El bloqueo serializa las sesiones de UN proceso. La API no ofrece compare-and-swap:
no hay exclusión distribuida frente a otro despliegue o editores manuales simultáneos.
"""
from copy import deepcopy
from threading import RLock

import gspread
from google.oauth2.service_account import Credentials

from core.models import ConflictError, ValidationError
from core.tournament import validar_estado
from services.serialization import HEADERS, TABS, decode, encode, fingerprint

_LOCK = RLock()


def conectar_google_sheets(service_account: dict, sheet_id: str):
    credentials = Credentials.from_service_account_info(
        dict(service_account), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    client = gspread.authorize(credentials)
    client.set_timeout(30)
    return GoogleSheetsRepository(client.open_by_key(sheet_id))


def cell(value):
    if isinstance(value, bool):
        return {"userEnteredValue": {"boolValue": value}}
    if isinstance(value, (int, float)):
        return {"userEnteredValue": {"numberValue": value}}
    # stringValue evita ejecutar como fórmulas nombres que comienzan por =, +, etc.
    return {"userEnteredValue": {"stringValue": str(value)}}


class GoogleSheetsRepository:
    def __init__(self, spreadsheet):
        self.spreadsheet = spreadsheet
        self.properties = {}
        self._initialized = False

    def initialize(self):
        with _LOCK:
            if self._initialized:
                return
            metadata = self.spreadsheet.fetch_sheet_metadata()
            self.properties = {s["properties"]["title"]: s["properties"] for s in metadata["sheets"]}
            missing = [tab for tab in TABS if tab not in self.properties]
            if missing:
                used = {s["sheetId"] for s in self.properties.values()}
                requests, next_id = [], 1
                for tab in missing:
                    while next_id in used:
                        next_id += 1
                    used.add(next_id)
                    props = {"sheetId": next_id, "title": tab,
                             "gridProperties": {"rowCount": 100, "columnCount": 20,
                                                "frozenRowCount": 2 if tab == "Grupos" else 1}}
                    self.properties[tab] = props
                    requests.append({"addSheet": {"properties": props}})
                    requests.append({"updateCells": {"start": {"sheetId": next_id},
                                     "rows": [{"values": [cell(v) for v in HEADERS[tab]]}],
                                     "fields": "userEnteredValue"}})
                self.spreadsheet.batch_update({"requests": requests})
            self._initialized = True

    def _tables(self):
        self.initialize()
        response = self.spreadsheet.values_batch_get(
            [f"'{tab}'" for tab in TABS],
            params={"valueRenderOption": "UNFORMATTED_VALUE"})
        return {tab: r.get("values", []) for tab, r in zip(TABS, response["valueRanges"])}

    def read(self):
        with _LOCK:
            tables = self._tables()
            return decode(tables), fingerprint(tables)

    def transact(self, revision, operation):
        with _LOCK:
            original = self._tables()
            if fingerprint(original) != revision:
                raise ConflictError("Los datos cambiaron en Google Sheets. Actualiza y vuelve a intentar.")
            state = deepcopy(decode(original))
            operation(state)
            validar_estado(state)
            updated = encode(state)
            # Relectura justo antes del commit: detecta ediciones mientras se calculaba.
            if fingerprint(self._tables()) != revision:
                raise ConflictError("Se detectó una edición concurrente. No se escribió ningún cambio.")
            requests = []
            for tab, rows in updated.items():
                props = self.properties[tab]
                sheet_id = props["sheetId"]
                old = original.get(tab, [])
                height = max(len(rows), len(old), 2)
                width = max([len(r) for r in rows + old] or [1])
                grid = props["gridProperties"]
                if height > grid["rowCount"] or width > grid["columnCount"]:
                    grid = {"rowCount": max(height, grid["rowCount"]),
                            "columnCount": max(width, grid["columnCount"])}
                    requests.append({"updateSheetProperties": {"properties": {"sheetId": sheet_id,
                                     "gridProperties": grid}, "fields": "gridProperties(rowCount,columnCount)"}})
                # El rango completo limpia también valores antiguos que ya no existen.
                requests.append({"updateCells": {"range": {"sheetId": sheet_id, "startRowIndex": 0,
                                 "endRowIndex": height, "startColumnIndex": 0, "endColumnIndex": width},
                                 "rows": [{"values": [cell(v) for v in row]} for row in rows],
                                 "fields": "userEnteredValue"}})
                requests.append({"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0,
                                 "endRowIndex": 1, "endColumnIndex": width},
                                 "cell": {"userEnteredFormat": {"backgroundColor": {"red": .07, "green": .20, "blue": .22},
                                          "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}}},
                                 "fields": "userEnteredFormat"}})
            # Un solo batchUpdate: configuración, grupos, equipos y resultados juntos.
            self.spreadsheet.batch_update({"requests": requests})
            self._initialized = False  # refresca dimensiones después de expandir
            return self.read()


def leer_configuracion(repo, competencia):
    return repo.read()[0].competitions[competencia].config


def leer_equipos(repo, competencia):
    return repo.read()[0].competitions[competencia].teams


def leer_partidos(repo, competencia):
    return repo.read()[0].competitions[competencia].matches


def leer_clasificados(repo, competencia):
    from services.serialization import clasificados_actuales
    return clasificados_actuales(repo.read()[0].competitions[competencia])


def guardar_equipos(repo, revision, competencia, equipos):
    def operation(state):
        c = state.competitions[competencia]
        if c.config.torneo_iniciado:
            raise ValidationError("Usa editar_equipo para conservar identidades durante el torneo.")
        c.teams = deepcopy(equipos)
    return repo.transact(revision, operation)


def guardar_grupos(repo, revision, competencia, sorteo=False, genericos=False):
    from core.tournament import iniciar_grupos
    return repo.transact(revision, lambda s: iniciar_grupos(s.competitions[competencia], sorteo, genericos))


def guardar_partido(repo, revision, competencia, id_partido, ganador, confirmar=False):
    # No se insertan partidos aislados: las rondas se crean completas.
    from core.eliminatorias import actualizar_ganador
    return repo.transact(revision, lambda s: actualizar_ganador(s.competitions[competencia], id_partido, ganador, confirmar))


actualizar_ganador = guardar_partido
