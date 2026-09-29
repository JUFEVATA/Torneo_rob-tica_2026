from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from core.models import Config, ConflictError, State, ValidationError
from core.tournament import crear_competencia, editar_equipo, iniciar_eliminatorias, reiniciar
from services.google_sheets import GoogleSheetsRepository, MANAGED_TABS
from services.repository import LocalRepository
from services.serialization import HEADERS, TABS, decode, encode
from tests.test_core import finish, tournament
from utils.helpers import importar_csv, csv_seguro
import pandas as pd


class FakeSpreadsheet:
    """Simula valores y batchUpdate; un cliente nuevo lee el mismo servidor."""
    def __init__(self):
        self.props, self.tables, self.writes = {}, {}, []
        self.fail_write = False

    def fetch_sheet_metadata(self):
        return {"sheets": [{"properties": deepcopy(v)} for v in self.props.values()]}

    def values_batch_get(self, ranges, params):
        return {"valueRanges": [{"values": deepcopy(self.tables[r.strip("'")])} for r in ranges]}

    def batch_update(self, body):
        if self.fail_write:
            raise RuntimeError("Simulated API failure")
        self.writes.append(deepcopy(body))
        for request in body["requests"]:
            if "addSheet" in request:
                p = deepcopy(request["addSheet"]["properties"])
                self.props[p["title"]] = p
                self.tables[p["title"]] = []
            if "updateSheetProperties" in request:
                p = request["updateSheetProperties"]["properties"]
                title = next(t for t, v in self.props.items() if v["sheetId"] == p["sheetId"])
                self.props[title]["gridProperties"].update(p.get("gridProperties", {}))
            if "updateCells" in request:
                update = request["updateCells"]
                sid = update.get("range", update.get("start"))["sheetId"]
                title = next(t for t, v in self.props.items() if v["sheetId"] == sid)
                self.tables[title] = [[next(iter(c["userEnteredValue"].values())) for c in row["values"]] for row in update["rows"]]
        return {}


class PersistenceTests(unittest.TestCase):
    def test_tables_round_trip_and_group_columns(self):
        state, c = tournament()
        tables = encode(state)
        self.assertEqual(tables["Grupos"][0], [f"Grupo {g}" for g in "ABCDEF"])
        self.assertEqual(tables["Grupos"][1], ["Sumo"] * 6)
        self.assertEqual(tables["Grupos"][2][:3], ["Equipo 1", "Equipo 2", "Equipo 3"])
        self.assertEqual(decode(tables), state)

    def test_champion_round_trip(self):
        state, c = tournament()
        iniciar_eliminatorias(c)
        finish(c)
        tables = encode(state)
        self.assertEqual(tables["Resultados"][1][1], 1)
        self.assertEqual(tables["Resultados"][1][2], c.config.campeon)
        self.assertEqual(decode(tables), state)

    def test_bad_manual_boolean_and_winner_rejected(self):
        state, c = tournament(4, 2, 4)
        tables = encode(state)
        tables["Equipos"][1][HEADERS["Equipos"].index("clasificado")] = "maybe"
        with self.assertRaises(ValidationError):
            decode(tables)
        iniciar_eliminatorias(c)
        tables = encode(state)
        tables["Partidos"][1][HEADERS["Partidos"].index("ganador")] = "no-existe"
        with self.assertRaises(ValidationError):
            decode(tables)

    def test_restart_and_other_session_persistence(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            repo = LocalRepository(path)
            _, revision = repo.read()
            state, c = tournament()
            iniciar_eliminatorias(c)
            finish(c)
            repo.transact(revision, lambda s: s.competitions.update(deepcopy(state.competitions)))
            self.assertEqual(LocalRepository(path).read()[0], state)
            self.assertEqual(LocalRepository(path).read(), LocalRepository(path).read())

    def test_stale_write_and_failure_roll_back(self):
        with TemporaryDirectory() as folder:
            repo = LocalRepository(Path(folder) / "state.json")
            _, old_revision = repo.read()
            repo.transact(old_revision, lambda s: crear_competencia(s, Config("Sumo", 8, 2)))
            with self.assertRaises(ConflictError):
                repo.transact(old_revision, lambda s: s.competitions.clear())
            state, revision = repo.read()
            with self.assertRaises(ValidationError):
                repo.transact(revision, lambda s: setattr(s.competitions["Sumo"].config, "numero_grupos", 9))
            self.assertEqual(repo.read()[0], state)

    def test_two_simultaneous_sessions_only_one_commit(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            repo = LocalRepository(path)
            _, revision = repo.read()
            outcomes = []
            def write(name):
                try:
                    LocalRepository(path).transact(revision, lambda s: crear_competencia(s, Config(name, 8, 2)))
                    outcomes.append("ok")
                except ConflictError:
                    outcomes.append("conflict")
            threads = [Thread(target=write, args=(name,)) for name in ("A", "B")]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertCountEqual(outcomes, ["ok", "conflict"])
            self.assertEqual(len(repo.read()[0].competitions), 1)

    def test_google_initialization_and_atomic_commit(self):
        server = FakeSpreadsheet()
        repo = GoogleSheetsRepository(server)
        _, revision = repo.read()
        self.assertEqual(set(server.tables), set(MANAGED_TABS))
        state, _ = tournament()
        before = len(server.writes)
        saved, _ = repo.transact(revision, lambda s: s.competitions.update(state.competitions))
        self.assertEqual(len(server.writes) - before, 1)
        self.assertEqual(saved, state)
        self.assertEqual(GoogleSheetsRepository(server).read()[0], state)

    def test_google_manual_edits_and_stale_commit(self):
        server = FakeSpreadsheet()
        repo = GoogleSheetsRepository(server)
        _, revision = repo.read()
        state, _ = tournament()
        _, stale = repo.transact(revision, lambda s: s.competitions.update(state.competitions))
        server.tables["Grupos"][9][0] = "Nombre manual"
        self.assertEqual(repo.read()[0].competitions["Sumo"].teams[0].nombre_equipo, "Nombre manual")
        with self.assertRaises(ConflictError):
            repo.transact(stale, lambda s: None)

    def test_google_failed_batch_does_not_erase_data(self):
        server = FakeSpreadsheet()
        repo = GoogleSheetsRepository(server)
        state, revision = repo.read()
        server.fail_write = True
        with self.assertRaises(RuntimeError):
            repo.transact(revision, lambda s: crear_competencia(s, Config("Sumo", 8, 2)))
        self.assertEqual(repo.read()[0], state)

    def test_google_reset_clears_old_rows(self):
        server = FakeSpreadsheet()
        repo = GoogleSheetsRepository(server)
        _, revision = repo.read()
        state, _ = tournament()
        _, revision = repo.transact(revision, lambda s: s.competitions.update(state.competitions))
        state, _ = repo.transact(revision, lambda s: reiniciar(s.competitions["Sumo"], "Competencia completa", True))
        self.assertEqual(server.tables["Equipos"], [HEADERS["Equipos"]])
        self.assertFalse(state.competitions["Sumo"].teams)

    def test_formula_names_written_as_strings(self):
        from services.google_sheets import cell
        self.assertEqual(cell("=1+1"), {"userEnteredValue": {"stringValue": "=1+1"}})

    def test_csv_input_output(self):
        self.assertEqual(importar_csv(b"nombre_equipo;numero_participantes\nA;3\nB;2\n"), (["A", "B"], [3, 2]))
        with self.assertRaises(ValidationError):
            importar_csv(b"nombre_equipo,numero_participantes\nA,2.5\n")
        with self.assertRaises(ValidationError):
            importar_csv(b"name\nA")
        self.assertIn("'=1+1", csv_seguro(pd.DataFrame([{"nombre": "=1+1"}])).decode("utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
