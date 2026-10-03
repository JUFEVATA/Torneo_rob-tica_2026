from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from core.models import Config, State, ConflictError, ValidationError
from core.tournament import clasificar, crear_competencia, iniciar_eliminatorias, validar_estado
from core.eliminatorias import partidos_fase
from core.sheet_flow import apply_sheet_edits, stage_tables
from services.serialization import decode, fingerprint
from services.google_sheets import GoogleSheetsRepository
from services.repository import LocalRepository
from tests.test_core import tournament, finish
from tests.test_persistence import FakeSpreadsheet
from tests.test_line_racing import line_state, finish_phase


class RecoveryTests(unittest.TestCase):
    def repo(self):
        state,c=tournament(8,2,8);iniciar_eliminatorias(c);finish(c)
        crear_competencia(state,Config('Otra',8,2,sistema='Libre'))
        state.public_competition='Sumo'
        server=FakeSpreadsheet();repo=GoogleSheetsRepository(server)
        _,rev=repo.read();repo.transact(rev,lambda s:s.competitions.update(state.competitions))
        return server,repo

    def test_force_delete_invalid_visible_draft_preserves_other_competition_and_backup(self):
        server,repo=self.repo();original=deepcopy(repo.read()[0].competitions['Otra'])
        server.tables['Grupos'][9][1]='bad';server.tables['Final'][3][2]='bad'
        names,rev=repo.recovery_options();self.assertIn('Sumo',names)
        saved,_=repo.recover(rev,'Sumo','Eliminar')
        self.assertNotIn('Sumo',saved.competitions)
        self.assertEqual(saved.competitions['Otra'],original)
        self.assertEqual(next(iter(saved.recovery_backups.values()))['hojas']['Grupos'][9][1],'bad')
        self.assertEqual(repo.read()[0],saved)

    def test_force_delete_unparseable_config(self):
        server,repo=self.repo()
        row=next(r for r in server.tables['Configuracion'] if len(r)>1 and r[0]=='Sumo' and r[1]=='numero_equipos');row[2]='bad'
        with self.assertRaises(ValidationError):repo.read()
        _,rev=repo.recovery_options();saved,_=repo.recover(rev,'Sumo','Eliminar')
        self.assertEqual(list(saved.competitions),['Otra'])
        self.assertTrue(saved.recovery_backups)

    def test_force_restart_invalid_canonical_result_keeps_roster(self):
        server,repo=self.repo();before=repo.read()[0].competitions['Sumo']
        server.tables['Partidos'][1][6]='missing-id'
        _,rev=repo.recovery_options();saved,_=repo.recover(rev,'Sumo','Reiniciar resultados')
        current=saved.competitions['Sumo']
        self.assertEqual([(t.id_equipo,t.nombre_equipo,t.grupo) for t in current.teams],[(t.id_equipo,t.nombre_equipo,t.grupo) for t in before.teams])
        self.assertFalse(current.matches);self.assertFalse(current.config.campeon)
        self.assertTrue(all(t.estado=='Pendiente' for t in current.teams))
        self.assertEqual(repo.read()[0],saved)

    def test_force_restart_complete_unparseable_config(self):
        server,repo=self.repo()
        row=next(r for r in server.tables['Configuracion'] if len(r)>1 and r[0]=='Sumo' and r[1]=='numero_grupos');row[2]='bad'
        _,rev=repo.recovery_options();saved,_=repo.recover(rev,'Sumo','Reiniciar competencia')
        self.assertFalse(saved.competitions['Sumo'].teams)
        self.assertFalse(saved.competitions['Sumo'].config.torneo_iniciado)
        self.assertIn('Otra',saved.competitions)

    def test_force_recovery_stale_revision_rejected(self):
        server,repo=self.repo();_,rev=repo.recovery_options()
        server.tables['Grupos'][9][0]='Nombre distinto'
        with self.assertRaises(ConflictError):repo.recover(rev,'Sumo','Eliminar')
        self.assertIn('Sumo',decode(server.tables).competitions)

    def test_local_force_delete_broken_competition_payload(self):
        with TemporaryDirectory() as folder:
            state,c=tournament(4,2,4);data=state.to_dict();data['competitions']['Sumo']['config']['unknown']='bad'
            path=Path(folder)/'broken.json';path.write_text(json.dumps(data))
            repo=LocalRepository(path);names,rev=repo.recovery_options()
            self.assertIn('Sumo',names)
            saved,_=repo.recover(rev,'Sumo','Eliminar')
            self.assertFalse(saved.competitions);self.assertTrue(saved.recovery_backups)

    def test_force_restart_line_results(self):
        state,c=line_state();finish_phase(c,'Linea1')
        from core.recovery import force_operation
        force_operation(state,c.config.competencia,'Reiniciar resultados')
        self.assertEqual(c.config.fase_actual,'Linea1')
        self.assertEqual(len(c.teams),32);self.assertFalse(c.closed_phases)
        self.assertTrue(all(r['intentos']==['','',''] for r in c.timing['Linea1'].values()))
        validar_estado(state)

    def test_legacy_group_correction_after_final_preserves_unaffected_branch(self):
        state,c=tournament(8,2,8);iniciar_eliminatorias(c);finish(c)
        first=partidos_fase(c,'Cuartos');unaffected=deepcopy(first[1]);removed=first[0].equipo_1
        clasificar(c,removed,'Pendiente')
        validar_estado(state)
        self.assertEqual(partidos_fase(c,'Cuartos')[1],unaffected)
        self.assertFalse(c.config.campeon)
        self.assertEqual(partidos_fase(c,'Cuartos')[0].equipo_1,'')
        clasificar(c,removed,'Clasificado')
        validar_estado(state)

    def test_legacy_sheet_correction_after_final_clears_only_descendant(self):
        state,c=tournament(8,2,8);iniciar_eliminatorias(c);finish(c)
        tables=stage_tables(state);m=partidos_fase(c,'Cuartos')[0]
        other=deepcopy(partidos_fase(c,'Cuartos')[1])
        for r in tables['4tos']:
            if len(r)>4 and r[3]==m.id_partido:r[2]='Clasifica' if r[4]!=m.ganador else 'No clasifica'
        changed=apply_sheet_edits(state,tables);cc=changed.competitions['Sumo']
        self.assertNotEqual(partidos_fase(cc,'Cuartos')[0].ganador,m.ganador)
        self.assertEqual(partidos_fase(cc,'Cuartos')[1],other)
        self.assertFalse(cc.config.campeon);validar_estado(changed)


if __name__=='__main__':unittest.main()
