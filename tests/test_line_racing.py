from copy import deepcopy
import unittest
from core.models import Config, State, ValidationError
from core.tournament import crear_competencia, iniciar_grupos, validar_estado
from core import line_racing as race
from core.publication import podium
from core.sheet_flow import stage_tables, apply_sheet_edits
from services.serialization import encode, decode
from services.google_sheets import GoogleSheetsRepository
from tests.test_persistence import FakeSpreadsheet


def line_state(total=32):
    state = State()
    crear_competencia(state, Config("Seguidor de línea", total, 1, cupos_clasificados=min(16, max(n for n in (2,4,8,16,32) if n <= total)), sistema="Tiempos"))
    c = state.competitions["Seguidor de línea"]
    iniciar_grupos(c, genericos=True)
    return state, c


def record(ms=30000, faults=0, sanction="Sin sanción", order=0):
    return {"intentos": [race.format_time(ms), "No terminó", "No terminó"], "fallos": faults, "sancion": sanction, "desempate": order}


def finish_phase(c, phase):
    for i, tid in enumerate(list(c.rounds[phase])):
        race.set_record(c, phase, tid, record(20000 + i*100))
    race.close_phase(c, phase)


class RacingTests(unittest.TestCase):
    def test_exact_milliseconds_and_format(self):
        self.assertEqual(race.parse_time("01:02.345"), 62345)
        self.assertEqual(race.parse_time("00:59,999"), 59999)
        self.assertEqual(race.format_time(60000), "01:00.000")
        for text in ("00:60.000", "00:01.1000", "0.1", "00:00.000", "-1:03.000"):
            with self.assertRaises(ValidationError): race.parse_time(text)

    def test_full_four_phases_and_podium_round_trip(self):
        state, c = line_state()
        for phase, size in zip(race.PHASES, [32,16,8,4]):
            self.assertEqual(len(c.rounds[phase]), size)
            finish_phase(c, phase)
            validar_estado(state)
        self.assertEqual(c.config.fase_actual, "Finalizado")
        self.assertEqual(list(podium(c).values()), race.rank(c, "Linea4")[:3])
        self.assertEqual(decode(encode(state)), state)

    def test_best_of_three_and_90_second_limit(self):
        _, c = line_state(2); tid = c.teams[0].id_equipo
        race.set_record(c, "Linea1", tid, {"intentos": ["01:30.001", "01:30.000", "00:59.999"], "fallos": 0, "sancion": "Sin sanción", "desempate": 0})
        self.assertEqual(race.best(c, "Linea1", tid), 59999)
        race.set_record(c, "Linea1", tid, {**record(90001), "intentos": ["01:30.001"]*3})
        self.assertIsNone(race.best(c, "Linea1", tid))
        self.assertEqual(race.status(c, "Linea1", tid), "Sin tiempo válido")

    def test_three_faults_disqualify_and_two_are_allowed(self):
        _, c = line_state(2); tid = c.teams[0].id_equipo
        race.set_record(c, "Linea1", tid, record(faults=2))
        self.assertEqual(race.best(c, "Linea1", tid), 30000)
        race.set_record(c, "Linea1", tid, record(faults=3))
        self.assertIsNone(race.best(c, "Linea1", tid))
        self.assertIn("Descalificado", race.status(c, "Linea1", tid))

    def test_new_fault_allowance_each_phase(self):
        _, c = line_state(2)
        for i,t in enumerate(c.teams): race.set_record(c, "Linea1", t.id_equipo, record(30000+i, faults=2))
        race.close_phase(c, "Linea1")
        tid = c.teams[0].id_equipo
        race.set_record(c, "Linea2", tid, record(faults=2))
        self.assertEqual(race.best(c, "Linea2", tid), 30000)
        self.assertEqual(race.faults(c, "Linea2", tid), 2)

    def test_no_show_and_judge_disqualification(self):
        _, c = line_state(2)
        for t, sanction in zip(c.teams, ["No presentó", "Descalificado"]):
            race.set_record(c, "Linea1", t.id_equipo, {**race.blank_record(), "sancion": sanction})
        race.close_phase(c, "Linea1")
        self.assertFalse(race.rank(c, "Linea1"))
        self.assertFalse(c.config.campeon)

    def test_cannot_close_with_pending_attempts(self):
        _, c = line_state(2)
        race.set_record(c, "Linea1", c.teams[0].id_equipo, {**race.blank_record(), "intentos": ["00:30.000", "", ""]})
        with self.assertRaisesRegex(ValidationError, "Faltan"): race.close_phase(c, "Linea1")

    def test_cutoff_tie_requires_judge_order(self):
        _, c = line_state(18)
        for i, t in enumerate(c.teams): race.set_record(c, "Linea1", t.id_equipo, record(20000+min(i,15)*100))
        with self.assertRaisesRegex(ValidationError, "Empate"): race.close_phase(c, "Linea1")
        for order,t in enumerate(c.teams[15:],1): race.set_record(c, "Linea1", t.id_equipo, record(21500, order=order))
        race.close_phase(c, "Linea1")
        self.assertIn(c.teams[15].id_equipo,c.rounds["Linea2"])
        self.assertNotIn(c.teams[16].id_equipo,c.rounds["Linea2"])

    def test_final_tie_requires_judge_even_if_both_on_podium(self):
        _,c=line_state(4)
        for p in race.PHASES[:3]: finish_phase(c,p)
        for i,t in enumerate(c.rounds['Linea4']): race.set_record(c,'Linea4',t,record(20000+max(0,i-1)*100))
        with self.assertRaisesRegex(ValidationError, 'Empate'):race.close_phase(c,'Linea4')

    def test_earlier_correction_reopens_affected_phase_preserves_other_times(self):
        state,c=line_state()
        for p in race.PHASES:finish_phase(c,p)
        kept=c.teams[1].id_equipo; old=deepcopy(c.timing['Linea2'][kept])
        newly=c.teams[-1].id_equipo
        race.set_record(c,'Linea1',newly,record(10000))
        self.assertIn(newly,c.rounds['Linea2'])
        self.assertEqual(c.timing['Linea2'][kept],old)
        self.assertEqual(c.closed_phases,['Linea1'])
        self.assertEqual(c.config.fase_actual,'Linea2')
        self.assertFalse(c.config.campeon)
        validar_estado(state)

    def test_sheet_time_edit_and_close_updates_next_sheet(self):
        state,c=line_state(4);tables=stage_tables(state)
        for i,row in enumerate(tables['SL Fase 1']):
            if len(row)>10 and row[10]!='id_equipo':row[1:4]=[f'00:3{i}.001','No terminó','No terminó']
            if row and row[0]=='Estado de fase':row[1]='Cerrada'
        updated=apply_sheet_edits(state,tables)
        self.assertEqual(len(updated.competitions[c.config.competencia].rounds['Linea2']),4)
        self.assertEqual(len(stage_tables(updated)['SL Fase 2']),9)

    def test_invalid_time_preserved_other_tabs_still_editable(self):
        state,c=line_state(4);server=FakeSpreadsheet();repo=GoogleSheetsRepository(server)
        _,rev=repo.read();repo.transact(rev,lambda s:s.competitions.update(state.competitions))
        server.tables['SL Fase 1'][5][1]='bad time'
        current,rev=repo.read();self.assertIn('SL Fase 1',current.sync_issues)
        repo.transact(rev,lambda s:setattr(s.competitions[c.config.competencia].config,'numero_participantes',8))
        self.assertEqual(server.tables['SL Fase 1'][5][1],'bad time')
        self.assertEqual(repo.read()[0].competitions[c.config.competencia].config.numero_participantes,8)

    def test_closed_first_phase_sheet_correction_ignores_stale_later_rows(self):
        state,c=line_state()
        for p in race.PHASES:finish_phase(c,p)
        tables=stage_tables(state);newly=c.teams[-1].id_equipo
        row=next(r for r in tables['SL Fase 1'] if len(r)>10 and r[10]==newly)
        row[1]='00:10.001'
        updated=apply_sheet_edits(state,tables)
        self.assertEqual(updated.competitions[c.config.competencia].closed_phases,['Linea1'])
        validar_estado(updated)

    def test_two_participants_limit(self):
        state,c=line_state(2);c.teams[0].numero_participantes=3
        with self.assertRaisesRegex(ValidationError,'dos integrantes'):validar_estado(state)

    def test_resize_line_roster_below_16_adapts_internal_capacity(self):
        from core.group_board import resize_groups
        state,c=line_state()
        resize_groups(c,10,4,16)
        self.assertEqual(c.config.cupos_clasificados,8)
        self.assertEqual(len(c.rounds['Linea1']),10)
        self.assertEqual(len(c.reserve),22)
        validar_estado(state)

    def test_configure_line_before_start_below_16(self):
        from core.tournament import configurar
        state=State();crear_competencia(state,Config('Línea',32,4,cupos_clasificados=16,sistema='Tiempos'))
        c=state.competitions['Línea'];configurar(c,10,2,0,16)
        self.assertEqual(c.config.cupos_clasificados,8)
        iniciar_grupos(c,genericos=True);validar_estado(state)

    def test_native_time_formats_and_dropdowns(self):
        from services.sheet_style import line_format_requests
        state,_=line_state(4);rows=stage_tables(state)['SL Fase 1']
        req=line_format_requests(99,rows,len(rows),20)
        self.assertTrue(any(r.get('repeatCell',{}).get('cell',{}).get('userEnteredFormat',{}).get('numberFormat',{}).get('type')=='TEXT' for r in req))
        self.assertTrue(any(r.get('setDataValidation',{}).get('rule',{}).get('condition',{}).get('values')==[{'userEnteredValue':'Abierta'},{'userEnteredValue':'Cerrada'}] for r in req))


if __name__ == '__main__':unittest.main()
