"""Google Sheets = fuente persistente. Lecturas por lote y commits atómicos.

El bloqueo serializa las sesiones de UN proceso. La API no ofrece compare-and-swap:
no hay exclusión distribuida frente a otro despliegue o editores manuales simultáneos.
"""
from copy import deepcopy
from threading import RLock

import gspread
from google.oauth2.service_account import Credentials

from core.group_board import preserve_drafts
from services.sheet_style import board_format_requests
from core.models import ConflictError, ValidationError
from core.tournament import validar_estado
from core.sheet_flow import STAGE_TABS, STATES, stage_tables, apply_sheet_edits, normalized_rows
from services.serialization import HEADERS, TABS, decode, encode, fingerprint

MANAGED_TABS = list(TABS) + STAGE_TABS
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
        self.group_rule_count = 0

    def initialize(self):
        with _LOCK:
            if self._initialized:
                return
            metadata = self.spreadsheet.fetch_sheet_metadata()
            self.properties = {s["properties"]["title"]: s["properties"] for s in metadata["sheets"]}
            self.group_rule_count = next((len(s.get("conditionalFormats", [])) for s in metadata["sheets"] if s["properties"]["title"] == "Grupos"), 0)
            missing = [tab for tab in MANAGED_TABS if tab not in self.properties]
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
                                     "rows": [{"values": [cell(v) for v in HEADERS.get(tab, [])]}],
                                     "fields": "userEnteredValue"}})
                self.spreadsheet.batch_update({"requests": requests})
            self._initialized = True

    def _tables(self):
        self.initialize()
        response = self.spreadsheet.values_batch_get(
            [f"'{tab}'" for tab in MANAGED_TABS],
            params={"valueRenderOption": "UNFORMATTED_VALUE"})
        return {tab: r.get("values", []) for tab, r in zip(MANAGED_TABS, response["valueRanges"])}

    def read(self):
        with _LOCK:
            tables = self._tables()
            state = decode(tables)
            # Las hojas visibles son entradas editables; las internas conservan el
            # historial. Una importación inválida no escribe ningún dato.
            updated = apply_sheet_edits(state, tables)
            projections = stage_tables(updated)
            preserve_drafts(projections["Grupos"], tables.get("Grupos", []))
            needs_sync = updated != state or any(
                normalized_rows(tables.get(tab, [])) != normalized_rows(rows)
                for tab, rows in projections.items())
            if needs_sync:
                self._commit(updated, tables)
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
            self._commit(state, original)
            tables = self._tables()
            return decode(tables), fingerprint(tables)

    def _commit(self, state, original):
        updated = encode(state)
        updated.update(stage_tables(state))
        preserve_drafts(updated["Grupos"], original.get("Grupos", []))
        if fingerprint(self._tables()) != fingerprint(original):
            raise ConflictError("Se detectó una edición concurrente. No se escribió ningún cambio.")
        requests = [{"updateSheetProperties": {"properties": {"sheetId": self.properties['Grupos']['sheetId'], "hidden": False, "index": 0}, "fields": "hidden,index"}}]
        for tab, rows in updated.items():
            props = self.properties[tab]
            sheet_id = props["sheetId"]
            visible = tab == 'Grupos' or tab in STAGE_TABS
            hidden = not visible or (tab == '32 avos' and not any(c.config.cupos_clasificados == 64 for c in state.competitions.values()))
            requests.append({"updateSheetProperties": {"properties": {"sheetId": sheet_id, "hidden": hidden}, "fields": "hidden"}})
            old = original.get(tab, [])
            height = max(len(rows), len(old), 2)
            width = max([len(r) for r in rows + old] or [1])
            if tab == "Grupos":
                width = max(width, 24)
            grid = props["gridProperties"]
            if height > grid["rowCount"] or width > grid["columnCount"]:
                requests.append({"updateSheetProperties": {"properties": {"sheetId": sheet_id,
                    "gridProperties": {"rowCount": max(height, grid["rowCount"]),
                                       "columnCount": max(width, grid["columnCount"])}},
                    "fields": "gridProperties(rowCount,columnCount)"}})
            if tab == "Grupos":
                requests.append({"unmergeCells": {"range": {"sheetId": sheet_id}}})
            requests.append({"updateCells": {"range": {"sheetId": sheet_id, "startRowIndex": 0,
                "endRowIndex": height, "startColumnIndex": 0, "endColumnIndex": width},
                "rows": [{"values": [cell(v) for v in row]} for row in rows],
                "fields": "userEnteredValue"}})
            requests.append({"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0,
                "endRowIndex": 1, "endColumnIndex": width},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": .051, "green": .588, "blue": .282},
                    "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}}},
                "fields": "userEnteredFormat"}})
            if tab == 'Grupos':
                requests.extend(board_format_requests(sheet_id, rows, height, max(width,grid['columnCount']), self.group_rule_count))
            elif tab in STAGE_TABS:
                status_col, id_col = (1, 2) if tab == 'Grupos' else (2, 4)
                requests.append({"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": height},
                    "cell": {"userEnteredFormat": {"backgroundColor": {"red": 1, "green": 1, "blue": 1},
                        "textFormat": {"fontFamily": "Arial", "fontSize": 11, "foregroundColor": {"red": .09, "green": .23, "blue": .24}},
                        "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"}}, "fields": "userEnteredFormat"}})
                requests.append({"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 0, "endIndex": height}, "properties": {"pixelSize": 32}, "fields": "pixelSize"}})
                for col, pixels in enumerate([430,180] if tab == 'Grupos' else [100,430,180]):
                    requests.append({"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": col, "endIndex": col+1}, "properties": {"pixelSize": pixels, "hiddenByUser": False}, "fields": "pixelSize,hiddenByUser"}})
                for index, row in enumerate(rows[1:], start=1):
                    if row and (str(row[0]).startswith(('Equipo ', 'Competencia:')) and len(row) == 1 or row[0] in ('Nombre del equipo', 'Partido')):
                        requests.append({"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": index, "endRowIndex": index+1, "endColumnIndex": status_col+1},
                            "cell": {"userEnteredFormat": {"backgroundColor": {"red": .624, "green": .812, "blue": .404}, "textFormat": {"bold": True}}}, "fields": "userEnteredFormat(backgroundColor,textFormat.bold)"}})
                # Limpia reglas antiguas al cambiar la cantidad de participantes.
                requests.append({"setDataValidation": {"range": {"sheetId": sheet_id,
                    "startColumnIndex": status_col, "endColumnIndex": status_col+1}}})
                for index, row in enumerate(rows):
                    if len(row) <= id_col or not row[id_col] or row[id_col] == 'id_equipo':
                        continue
                    requests.append({"setDataValidation": {"range": {"sheetId": sheet_id,
                        "startRowIndex": index, "endRowIndex": index+1,
                        "startColumnIndex": status_col, "endColumnIndex": status_col+1},
                        "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in STATES]},
                                 "strict": True, "showCustomUi": True}}})
                hidden_start = 2 if tab == 'Grupos' else 3
                requests.append({"updateDimensionProperties": {"range": {"sheetId": sheet_id,
                    "dimension": "COLUMNS", "startIndex": hidden_start,
                    "endIndex": max(width, grid['columnCount'])},
                    "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}})
        self.spreadsheet.batch_update({"requests": requests})
        self._initialized = False


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
