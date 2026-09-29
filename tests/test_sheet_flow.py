from copy import deepcopy
from pathlib import Path
import unittest
from core.models import State, ValidationError
from core.sheet_flow import (parse_rosters, import_roster, stage_tables, apply_sheet_edits,
                             active_participants, history_rows, PHASE_SHEETS, normalized_rows)
from services.google_sheets import GoogleSheetsRepository
from tests.test_persistence import FakeSpreadsheet

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples' / 'sumo2026.txt'


def imported():
    state = State()
    roster = parse_rosters([[EXAMPLE.read_text()]])[0]
    import_roster(state, roster)
    return state


class SheetFlowTests(unittest.TestCase):
    def test_full_pasted_list_and_separate_cells(self):
        text = EXAMPLE.read_text()
        single = parse_rosters([[text]])[0]
        separate = parse_rosters([[line] for line in text.splitlines()])[0]
        self.assertEqual(single, separate)
        self.assertEqual(len(single.entries), 85)
        self.assertEqual([sum(e[1] == g for e in single.entries) for g in 'ABCD'], [22,21,21,21])
        self.assertEqual(single.date, '29/09/2026 08:01:16 -0500')
        state = imported()
        self.assertEqual(state.competitions['Sumo'].config.cupos_clasificados, 32)
        self.assertEqual(apply_sheet_edits(state, stage_tables(state)), state)

    def test_duplicate_and_unbalanced_import_rejected(self):
        text = EXAMPLE.read_text()
        for bad in [text.replace('• Hercules', '• Fast and fusrious'), text.replace('• SALLE BOT X\n',''), text.replace('Grupos: 4', 'Grupos: 3')]:
            with self.assertRaises(ValidationError):
                parse_rosters([[bad]])

    def test_sheet_entire_tournament_current_and_history(self):
        state = imported()
        tables = stage_tables(state)
        teams = [r for r in tables['Grupos'] if len(r)==3 and r[2]!='id_equipo']
        for i,row in enumerate(teams):
            row[1] = 'Clasifica' if i<32 else 'No clasifica'
        state = apply_sheet_edits(state, tables)
        c = state.competitions['Sumo']
        self.assertEqual(len(c.matches),16)
        self.assertEqual(len(active_participants(c)),32)
        self.assertEqual(sum(r['Fase']=='Grupos' for r in history_rows(c)),85)
        for phase, expected in [('Dieciseisavos',16),('Octavos',8),('Cuartos',4),('Semifinal',2),('Final',1)]:
            tables = stage_tables(state)
            rows = [r for r in tables[PHASE_SHEETS[phase]] if len(r)==5 and r[3]!='id_partido']
            for row in rows[::2]:
                row[2] = 'Clasifica'
            state = apply_sheet_edits(state,tables)
            c = state.competitions['Sumo']
            self.assertEqual(len(active_participants(c)),expected)
            self.assertEqual(apply_sheet_edits(state,stage_tables(state)),state)
        self.assertTrue(c.config.campeon)
        self.assertEqual(len(history_rows(c)), 85+32+16+8+4+2)

    def test_conflicting_results_atomic_and_corrections_guarded(self):
        state = imported()
        tables = stage_tables(state)
        rows = [r for r in tables['Grupos'] if len(r)==3 and r[2]!='id_equipo']
        for i,row in enumerate(rows):
            row[1]='Clasifica' if i<32 else 'No clasifica'
        state = apply_sheet_edits(state,tables)
        tables = stage_tables(state)
        tables['16 avos'][3][2] = tables['16 avos'][4][2] = 'Clasifica'
        original = deepcopy(state)
        with self.assertRaises(ValidationError):
            apply_sheet_edits(state,tables)
        self.assertEqual(state,original)
        tables['16 avos'][4][2] = 'Pendiente'
        state = apply_sheet_edits(state,tables)
        tables = stage_tables(state)
        tables['16 avos'][3][2] = 'Pendiente'
        with self.assertRaises(ValidationError):
            apply_sheet_edits(state,tables)

    def test_read_persists_dropdowns_once_and_preserves_ids(self):
        server = FakeSpreadsheet()
        repo = GoogleSheetsRepository(server)
        _,rev=repo.read()
        state=imported()
        repo.transact(rev,lambda s:s.competitions.update(state.competitions))
        before=len(server.writes)
        for _ in range(3):
            self.assertEqual(repo.read()[0],state)
        self.assertEqual(len(server.writes),before)
        server.tables['Grupos'][7][1]='Clasifica'
        updated,_=repo.read()
        self.assertEqual(updated.competitions['Sumo'].teams[0].estado,'Clasificado')
        self.assertEqual(len(server.writes),before+1)
        self.assertEqual(updated.competitions['Sumo'].teams[0].id_equipo,state.competitions['Sumo'].teams[0].id_equipo)
        server.tables={tab:normalized_rows(rows) for tab,rows in server.tables.items()}
        before=len(server.writes)
        repo.read()
        self.assertEqual(len(server.writes),before)
        self.assertTrue(any('setDataValidation' in r for r in server.writes[-1]['requests']))

    def test_pending_groups_remain_editable_and_bulk_paste_replaces_old_cells(self):
        state = imported()
        tables = stage_tables(state)
        rows = [r for r in tables['Grupos'] if len(r)==3 and r[2]!='id_equipo']
        for row in rows[:32]:
            row[1]='Clasifica'
        updated = apply_sheet_edits(state,tables)
        self.assertFalse(updated.competitions['Sumo'].matches)
        self.assertEqual(len(active_participants(updated.competitions['Sumo'])),85)
        tables = stage_tables(state)
        tables['Grupos'][0][0] = EXAMPLE.read_text()
        self.assertEqual(len(parse_rosters(tables['Grupos'])),1)
        self.assertEqual(len(apply_sheet_edits(state,tables).competitions['Sumo'].teams),85)
