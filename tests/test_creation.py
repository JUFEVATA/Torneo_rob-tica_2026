from copy import deepcopy
import unittest
from core.models import State,Config,ValidationError
from core.tournament import crear_competencia_lista,validar_estado
from core.publication import archive
from core.recovery import recover_tables
from core import line_racing as race
from core.sheet_flow import stage_tables
from core.sheet_flow import Roster, import_roster
from services.serialization import encode
from services.google_sheets import GoogleSheetsRepository
from tests.test_persistence import FakeSpreadsheet
from tests.test_line_racing import finish_phase


class CreationTests(unittest.TestCase):
    def test_ready_creation_rejects_invalid_names_without_partial_competition(self):
        state=State()
        with self.assertRaises(ValidationError):
            crear_competencia_lista(state,Config('Línea',4,2,cupos_clasificados=4,sistema='Tiempos'),['Uno','uno'])
        self.assertFalse(state.competitions)
        crear_competencia_lista(state,Config('Línea',4,2,cupos_clasificados=4,sistema='Tiempos'),['Robot A','Robot B'])
        self.assertEqual([t.nombre_equipo for t in state.competitions['Línea'].teams],['Robot A','Robot B','Equipo 1','Equipo 2'])
        before=deepcopy(state)
        with self.assertRaises(ValidationError):
            crear_competencia_lista(state,Config('Línea',4,2,cupos_clasificados=4,sistema='Tiempos'))
        self.assertEqual(state,before);validar_estado(state)

    def test_sheet_delete_recreate_line_restores_groups_and_native_time_format(self):
        server=FakeSpreadsheet();repo=GoogleSheetsRepository(server)
        _,rev=repo.read()
        create=lambda s:crear_competencia_lista(s,Config('Línea',10,3,cupos_clasificados=8,sistema='Tiempos'))
        state,rev=repo.transact(rev,create)
        old_ids={t.id_equipo for t in state.competitions['Línea'].teams}
        state,rev=repo.transact(rev,lambda s:archive(s,'Línea'))
        self.assertEqual(len(server.tables['SL Fase 1']),4)
        state,rev=repo.transact(rev,create)
        self.assertEqual(len(server.tables['SL Fase 1']),16)
        self.assertEqual(server.tables['SL Fase 1'][3],race.HEADER)
        self.assertEqual(len(state.competitions['Línea'].timing['Linea1']),10)
        self.assertTrue(old_ids.isdisjoint(t.id_equipo for t in state.competitions['Línea'].teams))
        self.assertTrue(any(row and row[0]=='Competencia: Línea' for row in server.tables['Grupos']))
        requests=server.writes[-1]['requests']
        for tab in race.SHEETS.values():
            sid=server.props[tab]['sheetId']
            self.assertTrue(any(r.get('updateSheetProperties',{}).get('properties',{}).get('sheetId')==sid and r['updateSheetProperties']['properties'].get('hidden') is False for r in requests))
        self.assertTrue(any(r.get('repeatCell',{}).get('cell',{}).get('userEnteredFormat',{}).get('numberFormat',{}).get('pattern')=='000' for r in requests))
        self.assertEqual(repo.read()[0],state)

    def test_structural_line_tabs_survive_delete_without_timed_competitions(self):
        server = FakeSpreadsheet(); repo = GoogleSheetsRepository(server)
        _, rev = repo.read()
        _, rev = repo.transact(rev, lambda s: crear_competencia_lista(
            s, Config('Línea', 4, 2, cupos_clasificados=4, sistema='Tiempos')))
        _, rev = repo.transact(rev, lambda s: archive(s, 'Línea'))
        # El borrado limpia las filas del torneo, pero no elimina ni oculta la
        # plantilla de hojas que se reutilizará en la próxima creación.
        for tab in race.SHEETS.values():
            self.assertIn(tab, server.props)
            self.assertEqual(len(server.tables[tab]), 4)
            self.assertTrue(any(
                r.get('updateSheetProperties', {}).get('properties', {}).get('sheetId') == server.props[tab]['sheetId']
                and r['updateSheetProperties']['properties'].get('hidden') is False
                for r in server.writes[-1]['requests']))

    def test_force_delete_then_recreate_preserves_other_tournament_and_tabs(self):
        server = FakeSpreadsheet(); repo = GoogleSheetsRepository(server)
        _, rev = repo.read()
        def setup(s):
            crear_competencia_lista(s, Config('Sumo', 8, 2, cupos_clasificados=4, sistema='Libre'))
            crear_competencia_lista(s, Config('Línea', 40, 4, cupos_clasificados=32, sistema='Tiempos'))
        state, rev = repo.transact(rev, setup)
        other = deepcopy(state.competitions['Sumo'])
        ids = {tab: server.props[tab]['sheetId'] for tab in race.SHEETS.values()}
        state, rev = repo.recover(rev, 'Línea', 'Eliminar')
        state, rev = repo.read()
        for tab, sid in ids.items():
            self.assertEqual(server.props[tab]['sheetId'], sid)
            self.assertFalse(server.props[tab]['hidden'])
        state, rev = repo.transact(rev, lambda s: crear_competencia_lista(s, Config('Línea', 47, 4, cupos_clasificados=32, sistema='Tiempos')))
        self.assertEqual(state.competitions['Sumo'], other)
        self.assertEqual(len(state.competitions['Línea'].timing['Linea1']), 47)
        self.assertEqual(len(server.tables['SL Fase 1']), 53)
        self.assertEqual(repo.read()[0], state)

    def test_cached_repository_rebuilds_manually_removed_projection_tab(self):
        server = FakeSpreadsheet(); repo = GoogleSheetsRepository(server)
        _, rev = repo.read()
        state, rev = repo.transact(rev, lambda s: crear_competencia_lista(s, Config('Línea', 4, 2, cupos_clasificados=4, sistema='Tiempos')))
        del server.props['SL Fase 1']; del server.tables['SL Fase 1']
        self.assertEqual(repo.read()[0], state)
        self.assertEqual(len(server.tables['SL Fase 1']), 10)
        self.assertFalse(server.props['SL Fase 1']['hidden'])

    def test_enable_timing_keeps_ids_groups_and_backup_and_rejects_results(self):
        state = State()
        crear_competencia_lista(state, Config('Línea', 40, 4, cupos_clasificados=32, sistema='Libre'))
        before = deepcopy(state.competitions['Línea'])
        race.enable_timing(state, 'Línea')
        c = state.competitions['Línea']
        self.assertEqual(c.teams, before.teams)
        self.assertEqual(c.config.sistema, 'Tiempos')
        self.assertEqual(len(c.timing['Linea1']), 40)
        self.assertTrue(state.recovery_backups)
        validar_estado(state)
        crear_competencia_lista(state, Config('Sumo', 4, 2, cupos_clasificados=2, sistema='Libre'))
        state.competitions['Sumo'].teams[0].estado = 'Eliminado'
        with self.assertRaises(ValidationError): race.enable_timing(state, 'Sumo')

    def test_explicit_timed_import_repairs_existing_free_competition(self):
        state = State()
        crear_competencia_lista(state, Config('Seguidor de Linea', 4, 2, cupos_clasificados=4, sistema='Libre'))
        roster = Roster('Seguidor de Linea', groups=2, entries=[
            ('Equipo 1', 'A', 'Pendiente', ''), ('Equipo 2', 'A', 'Pendiente', ''),
            ('Equipo 3', 'B', 'Pendiente', ''), ('Equipo 4', 'B', 'Pendiente', ''),
        ])
        import_roster(state, roster, sistema='Tiempos')
        c = state.competitions['Seguidor de Linea']
        self.assertEqual(c.config.sistema, 'Tiempos')
        self.assertEqual(len(c.timing['Linea1']), 4)

    def test_delete_one_timed_competition_preserves_other_timed_sheet_and_backup(self):
        state = State()
        crear_competencia_lista(state, Config('Línea A', 4, 2, cupos_clasificados=4, sistema='Tiempos'))
        crear_competencia_lista(state, Config('Línea B', 4, 2, cupos_clasificados=4, sistema='Tiempos'))
        raw = encode(state); raw.update(stage_tables(state))
        recovered, safe = recover_tables(raw, 'Línea A', 'Eliminar')
        self.assertNotIn('Línea A', recovered.competitions)
        self.assertIn('Línea B', recovered.competitions)
        self.assertTrue(any(row and row[0] == 'Competencia: Línea B' for row in safe['SL Fase 1']))
        self.assertTrue(recovered.recovery_backups)
        self.assertEqual(recovered.archived[next(iter(recovered.archived))].config.competencia, 'Línea A')

    def test_unified_recovery_restarts_current_phase_with_backup(self):
        state=State();crear_competencia_lista(state,Config('Línea',4,2,cupos_clasificados=4,sistema='Tiempos'))
        c=state.competitions['Línea'];finish_phase(c,'Linea1')
        tid=next(iter(c.rounds['Linea2']));race.set_record(c,'Linea2',tid,{'intentos':['00:12.345','',''],'fallos':1,'sancion':'Sin sanción','desempate':0})
        first=deepcopy(c.timing['Linea1']);raw=encode(state);raw.update(stage_tables(state))
        recovered,_=recover_tables(raw,'Línea','Reiniciar fase actual')
        c=recovered.competitions['Línea'];self.assertEqual(c.timing['Linea1'],first)
        self.assertEqual(c.timing['Linea2'][tid],race.blank_record())
        self.assertTrue(recovered.recovery_backups);validar_estado(recovered)
