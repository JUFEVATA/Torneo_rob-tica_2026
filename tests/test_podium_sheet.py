from copy import deepcopy
import unittest

from core.podium_sheet import podium_rows
from core.publication import archive, restore, save_podium
from core.tournament import editar_equipo, iniciar_eliminatorias
from services.google_sheets import GoogleSheetsRepository
from tests.test_core import finish, tournament
from tests.test_persistence import FakeSpreadsheet


class PodiumSheetTests(unittest.TestCase):
    def setup_repo(self, state):
        server = FakeSpreadsheet()
        repo = GoogleSheetsRepository(server)
        _, rev = repo.read()
        repo.transact(rev, lambda s: s.competitions.update(deepcopy(state.competitions)))
        return server, repo

    def test_new_visible_sheet_preserves_saved_positions_and_has_dropdowns(self):
        state, c = tournament(8, 2, 8)
        save_podium(c, *[t.id_equipo for t in c.teams[:3]])
        server, repo = self.setup_repo(state)
        self.assertEqual(server.tables['Podio'], podium_rows(state))
        self.assertEqual(repo.read()[0], state)
        sid = server.props['Podio']['sheetId']
        requests = server.writes[-1]['requests']
        visibility = [r['updateSheetProperties']['properties'] for r in requests if 'updateSheetProperties' in r and r['updateSheetProperties']['properties']['sheetId'] == sid]
        self.assertTrue(any(p.get('hidden') is False for p in visibility))
        rules = [r['setDataValidation']['rule'] for r in requests if 'setDataValidation' in r and r['setDataValidation']['range']['sheetId'] == sid and 'rule' in r['setDataValidation']]
        self.assertEqual(len(rules), 3)
        self.assertEqual([v['userEnteredValue'] for v in rules[0]['condition']['values']], ['Por definir', *[t.nombre_equipo for t in c.teams]])

    def test_sheet_and_app_edits_persist_in_both_directions_without_repeated_writes(self):
        state, c = tournament(8, 2, 8)
        server, repo = self.setup_repo(state)
        for i, t in enumerate(c.teams[:3], 1):
            server.tables['Podio'][i][2] = t.nombre_equipo
        saved, rev = repo.read()
        self.assertEqual([getattr(saved.competitions['Sumo'].config, f'puesto_{i}') for i in (1, 2, 3)], [t.id_equipo for t in c.teams[:3]])
        self.assertEqual(saved.competitions['Sumo'].teams, c.teams)
        self.assertEqual(saved.competitions['Sumo'].matches, c.matches)
        repo.transact(rev, lambda s: save_podium(s.competitions['Sumo'], c.teams[3].id_equipo, '', c.teams[2].id_equipo))
        self.assertEqual([row[2] for row in server.tables['Podio'][1:]], [c.teams[3].nombre_equipo, 'Por definir', c.teams[2].nombre_equipo])
        writes = len(server.writes)
        for _ in range(3): repo.read()
        self.assertEqual(len(server.writes), writes)

    def test_invalid_podium_preserved_while_valid_group_edits_continue(self):
        state, c = tournament(8, 2, 8)
        server, repo = self.setup_repo(state)
        server.tables['Podio'][1][2] = server.tables['Podio'][2][2] = c.teams[0].nombre_equipo
        bad = deepcopy(server.tables['Podio'])
        server.tables['Grupos'][9][0] = 'Nombre nuevo'
        saved, _ = repo.read()
        self.assertIn('Podio', saved.sync_issues)
        self.assertEqual(server.tables['Podio'], bad)
        self.assertEqual(saved.competitions['Sumo'].teams[0].nombre_equipo, 'Nombre nuevo')
        self.assertFalse(saved.competitions['Sumo'].config.puesto_1)
        server.tables['Podio'][2][2] = 'Por definir'
        server.tables['Podio'][1][2] = 'Nombre nuevo'
        saved, _ = repo.read()
        self.assertFalse(getattr(saved, 'sync_error', ''))
        self.assertEqual(saved.competitions['Sumo'].config.puesto_1, c.teams[0].id_equipo)
        self.assertEqual(server.tables['Podio'][1][2], 'Nombre nuevo')

    def test_automatic_champion_is_not_frozen_when_editing_third_place(self):
        state, c = tournament(8, 2, 8)
        iniciar_eliminatorias(c)
        finish(c)
        server, repo = self.setup_repo(state)
        automatic = {row[3] for row in server.tables['Podio'][1:3]}
        third = next(t for t in c.teams if t.id_equipo not in automatic)
        server.tables['Podio'][3][2] = third.nombre_equipo
        saved, rev = repo.read()
        self.assertFalse(saved.competitions['Sumo'].config.puesto_1)
        self.assertFalse(saved.competitions['Sumo'].config.puesto_2)
        self.assertEqual(saved.competitions['Sumo'].config.puesto_3, third.id_equipo)
        renamed = c.name(c.config.campeon) + ' nuevo'
        repo.transact(rev, lambda s: editar_equipo(s.competitions['Sumo'], c.config.campeon, nombre=renamed, participantes=0))
        self.assertEqual(server.tables['Podio'][1][2], renamed)

    def test_archive_and_restore_rebuilds_podium_without_losing_positions(self):
        state, c = tournament(8, 2, 8)
        save_podium(c, c.teams[0].id_equipo, '', '')
        server, repo = self.setup_repo(state)
        _, rev = repo.read()
        saved, rev = repo.transact(rev, lambda s: archive(s, 'Sumo'))
        self.assertEqual(len(server.tables['Podio']), 1)
        repo.transact(rev, lambda s: restore(s, next(iter(saved.archived))))
        self.assertEqual(server.tables['Podio'], podium_rows(state))
        self.assertEqual(repo.read()[0].competitions['Sumo'], c)
