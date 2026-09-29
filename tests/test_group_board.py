from copy import deepcopy
import unittest
from core.group_board import board_rows, parse_board, resize_groups, preserve_drafts, value
from core.sheet_flow import stage_tables, apply_sheet_edits
from core.models import State, ValidationError
from core.tournament import validar_estado
from services.serialization import encode,decode
from services.google_sheets import GoogleSheetsRepository
from tests.test_persistence import FakeSpreadsheet
from tests.test_sheet_flow import imported


class BoardTests(unittest.TestCase):
    def test_six_cards_per_row_and_roundtrip(self):
        state=imported();c=state.competitions['Sumo']
        resize_groups(c,54,8,32)
        validar_estado(state)
        rows=board_rows(state)
        self.assertEqual([value(rows,8,col) for col in range(0,24,4)],[f'Equipo {n}' for n in range(1,7)])
        self.assertEqual([sum(t.grupo==g for t in c.teams) for g in 'ABCDEFGH'],[7,7,7,7,7,7,6,6])
        self.assertEqual(apply_sheet_edits(state,stage_tables(state)),state)
        self.assertEqual(decode(encode(state)),state)
        self.assertEqual(State.from_dict(state.to_dict()),state)

    def test_reduce_restore_ids_and_increase_placeholders(self):
        state=imported();c=state.competitions['Sumo']
        ids=[t.id_equipo for t in c.teams]
        resize_groups(c,54,8,32)
        self.assertEqual(len(c.reserve),31)
        resize_groups(c,85,4,32)
        self.assertEqual([t.id_equipo for t in c.teams],ids)
        self.assertFalse(c.reserve)
        resize_groups(c,90,4,32)
        self.assertEqual(len(c.teams),90)
        self.assertEqual(c.teams[-1].nombre_equipo,'Equipo nuevo 5')
        validar_estado(state)

    def test_draft_survives_reads_and_status_updates_until_checkbox(self):
        server=FakeSpreadsheet();repo=GoogleSheetsRepository(server)
        _,rev=repo.read(); state=imported()
        repo.transact(rev,lambda s:s.competitions.update(state.competitions))
        server.tables['Grupos'][4][1]=54
        server.tables['Grupos'][4][5]=8
        before=len(server.writes)
        saved,_=repo.read()
        self.assertEqual(saved,state)
        self.assertEqual(server.tables['Grupos'][4][1],54)
        self.assertEqual(len(server.writes),before)
        server.tables['Grupos'][4][13]=True
        saved,_=repo.read()
        self.assertEqual(len(saved.competitions['Sumo'].teams),54)
        self.assertEqual(len(saved.competitions['Sumo'].reserve),31)
        self.assertEqual(saved.competitions['Sumo'].config.numero_grupos,8)
        self.assertIs(server.tables['Grupos'][4][13],False)
        before=len(server.writes)
        self.assertEqual(repo.read()[0],saved)
        self.assertEqual(len(server.writes),before)

    def test_decided_results_lock_redistribution_and_bad_counts_atomic(self):
        state=imported()
        for total,groups,cupos in [(1,1,2),(85,86,32),(20,4,32),(85,4,3)]:
            tables=stage_tables(state)
            tables['Grupos'][4][1],tables['Grupos'][4][5],tables['Grupos'][4][9]=total,groups,cupos
            tables['Grupos'][4][13]=True
            with self.assertRaises(ValidationError):apply_sheet_edits(state,tables)
        tables=stage_tables(state)
        tables['Grupos'][9][1]='Clasifica'
        state=apply_sheet_edits(state,tables)
        tables=stage_tables(state);tables['Grupos'][4][5]=8;tables['Grupos'][4][13]=True
        with self.assertRaises(ValidationError):apply_sheet_edits(state,tables)
        self.assertEqual(state.competitions['Sumo'].config.numero_grupos,4)

    def test_id_and_missing_card_rejected(self):
        state=imported()
        for col in (2,6):
            tables=stage_tables(state);tables['Grupos'][8][col]=''
            with self.assertRaises(ValidationError):apply_sheet_edits(state,tables)
        tables=stage_tables(state);tables['Grupos'][9][2]='bad-id'
        with self.assertRaises(ValidationError):apply_sheet_edits(state,tables)

    def test_legacy_vertical_list_migrates_without_changing_state(self):
        from core.sheet_flow import group_rows
        state=imported();tables=stage_tables(state);tables['Grupos']=group_rows(state)
        self.assertEqual(apply_sheet_edits(state,tables),state)

    def test_negative_prefix_name_preserved_and_multi_competition(self):
        state=imported();state.competitions['Sumo'].teams[0].nombre_equipo='-robot'
        from core.sheet_flow import parse_rosters,import_roster
        import_roster(state,parse_rosters([['TORNEOS DE ROBÓTICA\nCompetencia: Carrera\nParticipantes: 4 | Grupos: 2\nEquipo 1\n• Uno\n• Dos\nEquipo 2\n• Tres\n• Cuatro']])[0])
        self.assertEqual(apply_sheet_edits(state,stage_tables(state)),state)
        tables=stage_tables(state)
        tables['Grupos'][4][5]=8;tables['Grupos'][4][13]=True
        saved=apply_sheet_edits(state,tables)
        self.assertEqual(saved.competitions['Carrera'],state.competitions['Carrera'])

    def test_invalid_sheet_decisions_keep_public_state_and_do_not_overwrite(self):
        from core.tournament import iniciar_eliminatorias
        from tests.test_core import tournament
        state,c=tournament(4,2,4);iniciar_eliminatorias(c)
        server=FakeSpreadsheet();repo=GoogleSheetsRepository(server)
        _,rev=repo.read();repo.transact(rev,lambda s:s.competitions.update(state.competitions))
        server.tables['Semifinal'][3][2]='Clasifica'
        server.tables['Semifinal'][4][2]='Clasifica'
        before=len(server.writes)
        saved,rev=repo.read()
        self.assertEqual(saved,state)
        self.assertTrue(saved.sync_error)
        self.assertEqual(len(server.writes),before)
        with self.assertRaises(ValidationError):repo.transact(rev,lambda s:None)
        self.assertEqual(server.tables['Semifinal'][4][2],'Clasifica')
