from copy import deepcopy
import unittest
from core.models import State, Config, ValidationError
from core.publication import public_name, publish, shown_stage, podium, save_podium, archive, restore
from core.sheet_flow import stage_tables, apply_sheet_edits
from core.tree import tree_svg
from core.tournament import crear_competencia, validar_estado
from services.serialization import encode, decode
from services.google_sheets import GoogleSheetsRepository
from tests.test_free_rounds import free_state
from tests.test_persistence import FakeSpreadsheet


class PublicationTests(unittest.TestCase):
    def test_public_selection_and_manual_stage_persist_independently(self):
        state, c = free_state()
        crear_competencia(state, Config("Carrera", 8, 2, sistema="Libre"))
        self.assertEqual(public_name(state), "Sumo")
        publish(state, "Carrera", "Semifinal")
        self.assertEqual(public_name(state), "Carrera")
        self.assertEqual(shown_stage(state.competitions["Carrera"]), "Semifinal")
        self.assertEqual(state.competitions["Carrera"].config.fase_actual, "Inscripción")
        self.assertEqual(decode(encode(state)), state)
        self.assertEqual(State.from_dict(state.to_dict()), state)
        publish(state, "Sumo")
        self.assertEqual(shown_stage(c), c.config.fase_actual)

    def test_podium_survives_sheet_sync_and_rejects_duplicate_or_unknown_teams(self):
        state, c = free_state()
        ids = [t.id_equipo for t in c.teams[:3]]
        save_podium(c, *ids)
        publish(state, "Sumo", "Finalizado")
        self.assertEqual(podium(c), dict(enumerate(ids, 1)))
        tables = stage_tables(state); tables["Grupos"][9][1] = "Clasifica"
        updated = apply_sheet_edits(state, tables)
        self.assertEqual(podium(updated.competitions["Sumo"]), podium(c))
        self.assertEqual(updated.competitions["Sumo"].config.etapa_publica, "Finalizado")
        self.assertEqual(decode(encode(updated)), updated)
        for args in [(ids[0], ids[0], ""), ("unknown", "", "")]:
            with self.assertRaises(ValidationError): save_podium(c, *args)

    def test_archive_restore_all_data_in_google_repository(self):
        state, c = free_state()
        from core.free_rounds import classify
        classify(c, "Grupos", c.teams[0].id_equipo, "Clasificado")
        classify(c, "Dieciseisavos", c.teams[0].id_equipo, "Clasificado")
        save_podium(c, *[t.id_equipo for t in c.teams[:3]])
        publish(state, "Sumo", "Octavos")
        original = deepcopy(c)
        crear_competencia(state, Config("Carrera", 8, 2, sistema="Libre"))
        server = FakeSpreadsheet(); repo = GoogleSheetsRepository(server)
        _, rev = repo.read()
        state, rev = repo.transact(rev, lambda s: s.competitions.update(state.competitions))
        state, rev = repo.transact(rev, lambda s: archive(s, "Sumo"))
        self.assertNotIn("Sumo", state.competitions)
        self.assertNotIn("Sumo", str(server.tables["Grupos"]))
        self.assertNotIn("free:", str(server.tables["16 avos"]))
        self.assertEqual(len(state.archived), 1)
        state, rev = GoogleSheetsRepository(server).read()
        key = next(iter(state.archived))
        self.assertEqual(state.archived[key], original)
        state, _ = repo.transact(rev, lambda s: restore(s, key))
        self.assertEqual(state.competitions["Sumo"], original)
        self.assertFalse(state.archived)
        self.assertIn("Carrera", state.competitions)

    def test_archive_all_and_restore_with_conflicting_name(self):
        state, c = free_state(); publish(state, "Sumo")
        archive(state, "Sumo"); validar_estado(state)
        self.assertIsNone(public_name(state))
        self.assertEqual(decode(encode(state)), state)
        key = next(iter(state.archived))
        crear_competencia(state, Config("Sumo", 8, 2))
        with self.assertRaises(ValidationError): restore(state, key)
        self.assertEqual(state.archived[key], c)

    def test_large_archive_is_split_and_roundtrips(self):
        state, c = free_state()
        c.config.titulo = "T" * 70000
        archive(state, "Sumo")
        tables = encode(state)
        self.assertGreater(len(tables["Papelera"]), 2)
        self.assertTrue(all(len(row[2]) <= 30000 for row in tables["Papelera"][1:]))
        self.assertEqual(decode(tables), state)

    def test_tree_has_team_names_and_escapes_markup(self):
        state, c = free_state()
        from core.free_rounds import classify
        c.teams[0].nombre_equipo = '<script>alert("x")</script>'
        classify(c, "Grupos", c.teams[0].id_equipo, "Clasificado")
        before = deepcopy(c)
        svg = tree_svg(c, "Dieciseisavos")
        self.assertIn("&lt;script&gt;", svg)
        self.assertNotIn("<script>", svg)
        self.assertIn("16avos de final", svg); self.assertIn("CAMPEÓN", svg)
        self.assertEqual(c, before)
