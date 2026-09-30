from copy import deepcopy
import unittest
from core.free_rounds import reconcile, classify, phases, active
from core.models import ValidationError
from core.sheet_flow import stage_tables, apply_sheet_edits, PHASE_SHEETS
from core.tournament import validar_estado
from services.serialization import encode, decode
from services.google_sheets import GoogleSheetsRepository
from tests.test_persistence import FakeSpreadsheet
from tests.test_sheet_flow import imported


def free_state():
    state=imported();c=state.competitions['Sumo'];c.config.sistema='Libre';reconcile(c)
    return state,c


def mark(rows,ids,status='Clasifica'):
    for row in rows:
        if len(row)>=5 and row[4] in ids:row[2]=status


class FreeRoundsTests(unittest.TestCase):
    def test_every_qualifier_advances_and_whole_tournament_roundtrips(self):
        state,c=free_state()
        for t in c.teams[:32]:classify(c,'Grupos',t.id_equipo,'Clasificado')
        for phase in phases(c):
            rows=stage_tables(state);entries=list(c.rounds[phase]);winners=entries[:len(entries)//2]
            mark(rows[PHASE_SHEETS[phase]],winners)
            state=apply_sheet_edits(state,rows);c=state.competitions['Sumo']
            validar_estado(state);self.assertEqual(decode(encode(state)),state)
            self.assertEqual(len(active(c)),len(winners))
        self.assertEqual(c.config.fase_actual,'Finalizado');self.assertEqual(len(active(c)),1)

    def test_two_teams_from_old_pair_can_advance_without_waiting(self):
        state,c=free_state()
        for t in c.teams[:32]:classify(c,'Grupos',t.id_equipo,'Clasificado')
        rows=stage_tables(state);ids=list(c.rounds['Dieciseisavos'])[:2]
        mark(rows['16 avos'],ids)
        state=apply_sheet_edits(state,rows);c=state.competitions['Sumo']
        self.assertEqual(set(c.rounds['Octavos']),set(ids))
        self.assertEqual(set(c.rounds['Octavos'].values()),{'Pendiente'})
        self.assertEqual(apply_sheet_edits(state,stage_tables(state)),state)
        rows=stage_tables(state);rows['Grupos'][4][5]=8
        saved=apply_sheet_edits(state,rows)
        self.assertEqual(saved.competitions['Sumo'].rounds,c.rounds)
        self.assertEqual(saved.competitions['Sumo'].config.numero_grupos,8)

    def test_correction_removes_only_affected_downstream_results(self):
        state,c=free_state()
        for t in c.teams[:4]:
            classify(c,'Grupos',t.id_equipo,'Clasificado')
            classify(c,'Dieciseisavos',t.id_equipo,'Clasificado')
            classify(c,'Octavos',t.id_equipo,'Clasificado')
        removed=c.teams[0].id_equipo;kept=c.teams[1].id_equipo
        rows=stage_tables(state);mark(rows['16 avos'],[removed],'No clasifica')
        saved=apply_sheet_edits(state,rows).competitions['Sumo']
        self.assertNotIn(removed,saved.rounds['Octavos']);self.assertNotIn(removed,saved.rounds['Cuartos'])
        self.assertEqual(saved.rounds['Octavos'][kept],'Clasificado')

    def test_invalid_round_does_not_block_group_count_and_keeps_manual_input(self):
        state,c=free_state()
        for t in c.teams[:32]:classify(c,'Grupos',t.id_equipo,'Clasificado')
        server=FakeSpreadsheet();repo=GoogleSheetsRepository(server);_,rev=repo.read()
        repo.transact(rev,lambda s:s.competitions.update(state.competitions))
        mark(server.tables['16 avos'],list(c.rounds['Dieciseisavos'])[:17])
        server.tables['Grupos'][4][5]=8
        saved,_=repo.read()
        self.assertTrue(saved.sync_error)
        self.assertEqual(saved.competitions['Sumo'].config.numero_grupos,8)
        self.assertEqual(sum(len(r)>2 and r[2]=='Clasifica' for r in server.tables['16 avos']),17)
        self.assertNotIn('Octavos',saved.competitions['Sumo'].rounds)

    def test_repository_transaction_incorporates_fresh_manual_decisions(self):
        state,c=free_state()
        classify(c,'Grupos',c.teams[0].id_equipo,'Clasificado')
        server=FakeSpreadsheet();repo=GoogleSheetsRepository(server);_,rev=repo.read()
        repo.transact(rev,lambda s:s.competitions.update(state.competitions))
        mark(server.tables['16 avos'],[c.teams[0].id_equipo])
        from services.serialization import fingerprint
        saved,_=repo.transact(fingerprint(repo._tables()),lambda s:None)
        self.assertIn(c.teams[0].id_equipo,saved.competitions['Sumo'].rounds['Octavos'])
