"""Google Sheets = fuente persistente. Lecturas por lote y commits atómicos.

El bloqueo serializa las sesiones de UN proceso. La API no ofrece compare-and-swap:
no hay exclusión distribuida frente a otro despliegue o editores manuales simultáneos.
"""
from copy import deepcopy
from threading import RLock

import gspread
from google.oauth2.service_account import Credentials

from core.group_board import preserve_drafts
from services.sheet_style import board_format_requests, podium_format_requests, line_format_requests
from core.models import ConflictError, ValidationError
from core.tournament import validar_estado
from core.sheet_flow import STAGE_TABS, STATES, stage_tables, apply_sheet_edits, normalized_rows
from services.serialization import HEADERS, TABS, decode, encode, fingerprint
from core.line_racing import SHEETS as LINE_SHEETS, HEADER_ROWS as LINE_HEADER_ROWS

MANAGED_TABS = list(TABS) + STAGE_TABS + list(LINE_SHEETS.values())
# Las hojas de tiempos forman parte de la plantilla del libro. Se mantienen
# visibles aunque no haya una competencia de seguidor de línea activa: eliminar
# una competencia nunca debe parecer que eliminó las pestañas del Excel.
STRUCTURAL_VISIBLE_TABS = {'Grupos', 'Podio', *STAGE_TABS, *LINE_SHEETS.values()}
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

    def initialize(self, refresh=False):
        with _LOCK:
            if not refresh and self._initialized and all(tab in self.properties for tab in MANAGED_TABS):
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
                             "hidden": tab not in STRUCTURAL_VISIBLE_TABS or tab == "32 avos",
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
        # Una pestaña puede haberse borrado u ocultado desde Excel/Sheets
        # después de crear este cliente compartido entre sesiones.
        self.initialize(refresh=True)
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
            try:
                updated = apply_sheet_edits(state, tables, strict=False)
            except ValidationError as error:
                # Un borrador inválido en la hoja no deja fuera de servicio al
                # público ni se sobrescribe. Se muestra el último estado válido.
                state.sync_error = str(error)
                return state, fingerprint(tables)
            projections = stage_tables(updated)
            for tab in getattr(updated, "sync_issues", {}):
                projections[tab] = tables[tab]
            preserve_drafts(projections["Grupos"], tables.get("Grupos", []))
            # Un despliegue en caliente puede haber escrito los valores nuevos
            # con un formateador anterior aún en memoria. Termina la migración
            # también cuando solo falta el encabezado nativo de cuatro filas.
            styles_pending = any(
                tab not in getattr(updated, "sync_issues", {}) and
                self.properties[tab]["gridProperties"].get("frozenRowCount", 0) != LINE_HEADER_ROWS
                for tab in LINE_SHEETS.values())
            visibility_pending = any(
                self.properties[tab].get("hidden", False)
                for tab in LINE_SHEETS.values())
            needs_sync = updated != state or styles_pending or visibility_pending or any(
                normalized_rows(tables.get(tab, [])) != normalized_rows(rows)
                for tab, rows in projections.items())
            if needs_sync:
                self._commit(updated, tables)
                tables = self._tables()
            result = decode(tables)
            if getattr(updated, "sync_issues", {}):
                result.sync_issues = updated.sync_issues
                result.sync_error = updated.sync_error
            return result, fingerprint(tables)

    def transact(self, revision, operation):
        with _LOCK:
            original = self._tables()
            if fingerprint(original) != revision:
                raise ConflictError("Los datos cambiaron en Google Sheets. Actualiza y vuelve a intentar.")
            state = deepcopy(decode(original))
            state = apply_sheet_edits(state, original, strict=False)  # incorpora decisiones válidas sin bloquear otras hojas
            operation(state)
            validar_estado(state)
            self._commit(state, original)
            tables = self._tables()
            return decode(tables), fingerprint(tables)

    def recovery_options(self):
        tables = self._tables()
        rows = tables.get("Configuracion", [])
        names = list(dict.fromkeys(str(r[0]) for r in rows[1:] if r and r[0]))
        return names, fingerprint(tables)

    def recover(self, revision, name, action):
        from core.recovery import recover_tables
        with _LOCK:
            original = self._tables()
            if fingerprint(original) != revision:
                raise ConflictError("Los datos cambiaron. Actualiza antes de recuperar el torneo.")
            state, safe_inputs = recover_tables(original, name, action)
            self._commit(state, original, preserved_issues=safe_inputs)
            tables = self._tables()
            return decode(tables), fingerprint(tables)

    def _commit(self, state, original, preserved_issues=None):
        updated = encode(state)
        updated.update(stage_tables(state))
        for tab in getattr(state, "sync_issues", {}):
            updated[tab] = (preserved_issues or original)[tab]
        preserve_drafts(updated["Grupos"], (preserved_issues or original).get("Grupos", []))
        if fingerprint(self._tables()) != fingerprint(original):
            raise ConflictError("Se detectó una edición concurrente. No se escribió ningún cambio.")
        requests = [{"updateSheetProperties": {"properties": {"sheetId": self.properties['Grupos']['sheetId'], "hidden": False, "index": 0}, "fields": "hidden,index"}}]
        for tab, rows in updated.items():
            props = self.properties[tab]
            sheet_id = props["sheetId"]
            # Las pestañas estructurales permanecen visibles y reutilizables.
            # El contenido se vacía al eliminar una competencia, pero la hoja
            # y su formato siguen existiendo para la siguiente creación.
            visible = tab in STRUCTURAL_VISIBLE_TABS
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
            if tab == "Grupos" or tab in STAGE_TABS or tab in LINE_SHEETS.values():
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
            elif tab == 'Podio':
                requests.extend(podium_format_requests(sheet_id, rows, height, max(width, grid['columnCount']), state))
            elif tab in LINE_SHEETS.values():
                requests.extend(line_format_requests(sheet_id, rows, height, max(width, grid['columnCount'])))
            elif tab in STAGE_TABS:
                for index, row in enumerate(rows):
                    if index == 0 or (len(row) == 1 and str(row[0]).startswith('Competencia:')):
                        requests.append({"mergeCells": {"range": {"sheetId": sheet_id, "startRowIndex": index, "endRowIndex": index+1, "startColumnIndex": 0, "endColumnIndex": 3}, "mergeType": "MERGE_ALL"}})
                status_col, id_col = (1, 2) if tab == 'Grupos' else (2, 4)
                requests.append({"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": height},
                    "cell": {"userEnteredFormat": {"backgroundColor": {"red": 1, "green": 1, "blue": 1},
                        "textFormat": {"fontFamily": "Arial", "fontSize": 11, "foregroundColor": {"red": .09, "green": .23, "blue": .24}},
                        "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"}}, "fields": "userEnteredFormat"}})
                requests.append({"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 0, "endIndex": height}, "properties": {"pixelSize": 32}, "fields": "pixelSize"}})
                for col, pixels in enumerate([430,180] if tab == 'Grupos' else [100,430,180]):
                    requests.append({"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": col, "endIndex": col+1}, "properties": {"pixelSize": pixels, "hiddenByUser": False}, "fields": "pixelSize,hiddenByUser"}})
                for index, row in enumerate(rows[1:], start=1):
                    if row and (str(row[0]).startswith(('Equipo ', 'Competencia:')) and len(row) == 1 or row[0] in ('Nombre del equipo', 'Partido', 'N.º')):
                        requests.append({"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": index, "endRowIndex": index+1, "endColumnIndex": status_col+1},
                            "cell": {"userEnteredFormat": {"backgroundColor": {"red": .624, "green": .812, "blue": .404}, "textFormat": {"bold": True}}}, "fields": "userEnteredFormat(backgroundColor,textFormat.bold)"}})
                # Limpia reglas antiguas al cambiar la cantidad de participantes.
                requests.append({"setDataValidation": {"range": {"sheetId": sheet_id,
                    "startColumnIndex": status_col, "endColumnIndex": status_col+1}}})
                for index, row in enumerate(rows):
                    if len(row) <= id_col or not row[id_col] or row[id_col] == 'id_equipo' or (tab in STAGE_TABS and not row[3]):
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
