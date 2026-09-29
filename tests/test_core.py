import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from core.eliminatorias import FASES, actualizar_ganador, fase_para, partidos_fase
from core.grupos import distribuir, nombre_columna
from core.models import Config, State, ValidationError
from core.tournament import (agregar_equipos, clasificar, completar_genericos, configurar,
                             crear_competencia, editar_equipo, eliminar_equipo,
                             iniciar_eliminatorias, iniciar_grupos, reiniciar, validar_estado)


def tournament(size=32, groups=6, qualified=32):
    state = State()
    crear_competencia(state, Config("Sumo", size, groups, 87, qualified))
    c = state.competitions["Sumo"]
    completar_genericos(c)
    iniciar_grupos(c)
    for t in c.teams[:qualified]:
        clasificar(c, t.id_equipo, "Clasificado")
    return state, c


def finish(c):
    while not c.config.campeon:
        phase = c.config.fase_actual
        for match in partidos_fase(c, phase):
            if not match.ganador:
                actualizar_ganador(c, match.id_partido, match.equipo_1)


class DistributionTests(unittest.TestCase):
    def test_required_examples(self):
        for total, groups, expected in [(10, 3, [4, 3, 3]), (17, 4, [5, 4, 4, 4]),
                                        (23, 5, [5, 5, 5, 4, 4]), (32, 6, [6, 6, 5, 5, 5, 5]),
                                        (32, 8, [4] * 8)]:
            with self.subTest(total=total, groups=groups):
                self.assertEqual(distribuir(total, groups), expected)

    def test_properties_all_small_combinations(self):
        for total in range(1, 200):
            for groups in range(1, total + 1):
                sizes = distribuir(total, groups)
                self.assertEqual(sum(sizes), total)
                self.assertLessEqual(max(sizes) - min(sizes), 1)
                self.assertEqual(sizes, sorted(sizes, reverse=True))
                self.assertGreater(min(sizes), 0)

    def test_excel_column_names(self):
        for number, name in [(1, "A"), (26, "Z"), (27, "AA"), (28, "AB"), (52, "AZ"), (703, "AAA")]:
            self.assertEqual(nombre_columna(number), name)
        with self.assertRaises(ValidationError):
            nombre_columna(0)

    def test_invalid_inputs(self):
        for args in [(0, 1), (1, 0), (-2, 3), (3, 4), (3.5, 2), (True, 1)]:
            with self.subTest(args=args), self.assertRaises(ValidationError):
                distribuir(*args)

    def test_circular_order(self):
        _, c = tournament(10, 3, 8)
        self.assertEqual([t.grupo for t in c.teams], list("ABCABCABCA"))
        self.assertEqual([t.nombre_equipo for t in c.teams if t.grupo == "A"], ["Equipo 1", "Equipo 4", "Equipo 7", "Equipo 10"])

    def test_random_keeps_counts_and_is_not_rerun(self):
        state, c = tournament(32, 6, 16)
        reiniciar(c, "Fase actual", True)
        iniciar_grupos(c, sorteo=True)
        counts = [sum(t.grupo == nombre_columna(i+1) for t in c.teams) for i in range(6)]
        self.assertEqual(counts, [6, 6, 5, 5, 5, 5])
        restored = State.from_dict(state.to_dict())
        self.assertEqual(state.to_dict(), restored.to_dict())
        with self.assertRaises(ValidationError):
            iniciar_grupos(c, sorteo=True)

    def test_more_than_26_groups(self):
        _, c = tournament(60, 28, 32)
        self.assertEqual(c.teams[27].grupo, "AB")


class TournamentTests(unittest.TestCase):
    def test_full_32_bracket(self):
        state, c = tournament()
        iniciar_eliminatorias(c)
        counts = []
        while not c.config.campeon:
            phase = c.config.fase_actual
            matches = partidos_fase(c, phase)
            counts.append((phase, len(matches) * 2))
            for m in matches:
                actualizar_ganador(c, m.id_partido, m.equipo_1)
                validar_estado(state)
        self.assertEqual(counts, [("Dieciseisavos", 32), ("Octavos", 16), ("Cuartos", 8), ("Semifinal", 4), ("Final", 2)])
        self.assertEqual(len(c.matches), 31)
        self.assertEqual(c.config.campeon, c.teams[0].id_equipo)
        self.assertEqual(c.config.fase_actual, "Finalizado")

    def test_all_supported_brackets(self):
        for size, phase in FASES.items():
            with self.subTest(size=size):
                state, c = tournament(size, 1, size)
                iniciar_eliminatorias(c)
                self.assertEqual(c.config.fase_actual, phase)
                finish(c)
                validar_estado(state)
                self.assertEqual(len(c.matches), size - 1)

    def test_wrong_qualification_count_and_duplicate_round(self):
        _, c = tournament(8, 2, 8)
        clasificar(c, c.teams[0].id_equipo, "Pendiente")
        with self.assertRaises(ValidationError):
            iniciar_eliminatorias(c)
        clasificar(c, c.teams[0].id_equipo, "Clasificado")
        iniciar_eliminatorias(c)
        with self.assertRaises(ValidationError):
            iniciar_eliminatorias(c)

    def test_pending_does_not_advance(self):
        _, c = tournament(8, 2, 8)
        iniciar_eliminatorias(c)
        for m in c.matches[:3]:
            actualizar_ganador(c, m.id_partido, m.equipo_1)
        self.assertEqual(len(c.matches), 4)
        self.assertEqual(c.config.fase_actual, "Cuartos")

    def test_only_participant_can_win(self):
        _, c = tournament(8, 2, 8)
        iniciar_eliminatorias(c)
        with self.assertRaises(ValidationError):
            actualizar_ganador(c, c.matches[0].id_partido, c.teams[-1].id_equipo)

    def test_correction_preserves_unaffected_branch(self):
        state, c = tournament(8, 2, 8)
        iniciar_eliminatorias(c)
        finish(c)
        first = partidos_fase(c, "Cuartos")[0]
        unaffected = deepcopy(partidos_fase(c, "Semifinal")[1])
        with self.assertRaises(ValidationError):
            actualizar_ganador(c, first.id_partido, first.equipo_2)
        actualizar_ganador(c, first.id_partido, first.equipo_2, True)
        self.assertEqual(partidos_fase(c, "Semifinal")[1], unaffected)
        self.assertEqual(partidos_fase(c, "Semifinal")[0].equipo_1, first.equipo_2)
        self.assertFalse(partidos_fase(c, "Semifinal")[0].ganador)
        self.assertFalse(partidos_fase(c, "Final")[0].ganador)
        self.assertFalse(c.config.campeon)
        validar_estado(state)
        finish(c)
        validar_estado(state)
        self.assertEqual(c.config.campeon, first.equipo_2)

    def test_clearing_previous_winner_blocks_later_play(self):
        state, c = tournament(8, 2, 8)
        iniciar_eliminatorias(c)
        finish(c)
        quarter = partidos_fase(c, "Cuartos")[0]
        actualizar_ganador(c, quarter.id_partido, "", True)
        semi = partidos_fase(c, "Semifinal")[0]
        self.assertEqual(semi.estado, "Por definir")
        with self.assertRaises(ValidationError):
            actualizar_ganador(c, semi.id_partido, semi.equipo_2)
        validar_estado(state)

    def test_each_reset_requires_confirmation(self):
        _, c = tournament()
        for scope in ["Fase actual", "Eliminatorias", "Competencia completa"]:
            with self.assertRaises(ValidationError):
                reiniciar(c, scope)

    def test_resets(self):
        state, c = tournament(8, 2, 8)
        iniciar_eliminatorias(c)
        finish(c)
        reiniciar(c, "Fase actual", True)
        self.assertEqual(c.config.fase_actual, "Final")
        self.assertEqual(sum(bool(m.ganador) for m in c.matches), 6)
        reiniciar(c, "Eliminatorias", True)
        self.assertFalse(c.matches)
        self.assertEqual(sum(t.clasificado for t in c.teams), 8)
        reiniciar(c, "Fase actual", True)
        self.assertFalse(c.config.torneo_iniciado)
        self.assertTrue(all(not t.grupo and not t.clasificado for t in c.teams))
        reiniciar(c, "Competencia completa", True)
        self.assertFalse(c.teams)
        validar_estado(state)

    def test_competitions_stay_isolated(self):
        state, c = tournament(8, 2, 8)
        crear_competencia(state, Config("Edison", 4, 2, 12, 4))
        edison = deepcopy(state.competitions["Edison"])
        iniciar_eliminatorias(c)
        finish(c)
        reiniciar(c, "Competencia completa", True)
        self.assertEqual(state.competitions["Edison"], edison)

    def test_duplicates_normalized(self):
        state = State()
        crear_competencia(state, Config("Sumo", 8, 2))
        c = state.competitions["Sumo"]
        for names in [["Neo Bots", " neo  bots "], ["A", "Ａ"]]:
            with self.assertRaises(ValidationError):
                agregar_equipos(c, names)
        agregar_equipos(c, ["A", "B"], [3, 2])
        with self.assertRaises(ValidationError):
            editar_equipo(c, c.teams[1].id_equipo, "a", 1)
        self.assertEqual(sum(t.numero_participantes for t in c.teams), 5)

    def test_rename_keeps_match_identity(self):
        state, c = tournament(4, 2, 4)
        iniciar_eliminatorias(c)
        team_id = c.teams[0].id_equipo
        editar_equipo(c, team_id, "Nombre real", 5)
        self.assertEqual(c.matches[0].equipo_1, team_id)
        self.assertEqual(c.name(team_id), "Nombre real")
        validar_estado(state)

    def test_structural_edits_locked_after_groups(self):
        _, c = tournament(4, 2, 4)
        for operation in [lambda: agregar_equipos(c, ["Nuevo"]), lambda: eliminar_equipo(c, c.teams[0].id_equipo),
                          lambda: configurar(c, 4, 1, 12, 4)]:
            with self.assertRaises(ValidationError):
                operation()

    def test_unsupported_qualification(self):
        for number in [0, 1, 3, 12, 128]:
            with self.assertRaises(ValidationError):
                fase_para(number)

    def test_self_match_rejected(self):
        state, c = tournament(4, 2, 4)
        iniciar_eliminatorias(c)
        c.matches[0].equipo_2 = c.matches[0].equipo_1
        with self.assertRaises(ValidationError):
            validar_estado(state)


if __name__ == "__main__":
    unittest.main()
