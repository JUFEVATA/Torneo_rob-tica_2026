"""Flujos reales de widgets con Streamlit AppTest y repositorio temporal."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from core.models import Config
from core.tournament import crear_competencia
from services.repository import LocalRepository
from services.runtime import read_state, login_limiter
from tests.test_core import tournament

APP = Path(__file__).resolve().parents[1] / "app.py"


def widget(collection, label):
    return next(w for w in collection if w.label == label)


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.repo = LocalRepository(Path(self.folder.name) / "data.json")
        self.env = patch.dict("os.environ", {"ROBOTICA_DEMO": "1"})
        self.backend = patch("services.runtime.get_repository", return_value=self.repo)
        self.env.start()
        self.backend.start()
        read_state.clear()
        login_limiter.clear()

    def tearDown(self):
        read_state.clear()
        self.backend.stop()
        self.env.stop()
        self.folder.cleanup()

    def app(self, admin=False):
        at = AppTest.from_file(str(APP), default_timeout=15)
        at.secrets["admin"] = {"password": "solo-prueba-temporal"}
        at.run()
        if admin:
            widget(at.text_input, "Contraseña").set_value("solo-prueba-temporal")
            widget(at.button, "Entrar").click().run()
        self.assertFalse(at.exception)
        return at

    def load_tournament(self):
        state, _ = tournament(8, 2, 8)
        _, revision = self.repo.read()
        self.repo.transact(revision, lambda s: s.competitions.update(state.competitions))

    def page(self, at, name):
        widget(at.radio, "Navegación").set_value(name).run()
        self.assertFalse(at.exception)

    def test_public_all_pages_have_no_write_actions(self):
        self.load_tournament()
        at = self.app()
        forbidden = {"GENERAR GRUPOS", "GENERAR ELIMINATORIAS", "Guardar equipo", "Confirmar reinicio", "Crear competencia", "✓ CLASIFICA"}
        for page in ["Inicio", "Configuración", "Equipos", "Grupos", "Clasificados", "Eliminatorias", "Cuadro", "Resultados", "Administración"]:
            self.page(at, page)
            self.assertFalse(forbidden.intersection(b.label for b in at.button))

    def test_admin_all_pages(self):
        self.load_tournament()
        at = self.app(True)
        for page in ["Inicio", "Configuración", "Equipos", "Grupos", "Clasificados", "Eliminatorias", "Cuadro", "Resultados", "Administración"]:
            self.page(at, page)

    def test_wrong_password_cannot_edit(self):
        self.load_tournament()
        at = self.app()
        widget(at.text_input, "Contraseña").set_value("incorrecta")
        widget(at.button, "Entrar").click().run()
        self.assertTrue(at.error)
        self.assertFalse(any(b.label == "Cerrar sesión" for b in at.button))

    def test_create_and_generate_groups_from_empty_app(self):
        at = self.app(True)
        widget(at.text_input, "Nombre de la competencia").set_value("Seguidor")
        widget(at.number_input, "Cantidad total de equipos").set_value(10)
        widget(at.number_input, "Cantidad de grupos").set_value(3)
        widget(at.selectbox, "Equipos que avanzan").set_value(8)
        widget(at.button, "Crear competencia").click().run()
        self.assertFalse(at.exception)
        self.page(at, "Configuración")
        widget(at.checkbox, "Completar equipos faltantes con nombres genéricos").check()
        widget(at.button, "GENERAR GRUPOS").click().run()
        self.assertFalse(at.exception)
        c = self.repo.read()[0].competitions["Seguidor"]
        self.assertEqual([t.grupo for t in c.teams], list("ABCABCABCA"))

    def test_entire_bracket_from_ui_and_new_session(self):
        self.load_tournament()
        at = self.app(True)
        self.page(at, "Clasificados")
        widget(at.button, "GENERAR ELIMINATORIAS").click().run()
        self.page(at, "Eliminatorias")
        for _ in range(7):
            buttons = [b for b in at.button if b.label.endswith(" gana") and not b.disabled]
            self.assertTrue(buttons)
            buttons[0].click().run()
            self.assertFalse(at.exception)
        self.assertTrue(self.repo.read()[0].competitions["Sumo"].config.campeon)
        public = self.app()
        self.page(public, "Resultados")
        self.assertTrue(any("CAMPEÓN" in m.value for m in public.markdown))
        self.assertFalse(any(b.label.endswith(" gana") for b in public.button))

    def test_reset_requires_checkbox_and_exact_name(self):
        self.load_tournament()
        at = self.app(True)
        self.page(at, "Administración")
        widget(at.selectbox, "Qué quieres reiniciar").set_value("Competencia completa")
        widget(at.button, "Confirmar reinicio").click().run()
        self.assertEqual(len(self.repo.read()[0].competitions["Sumo"].teams), 8)
        widget(at.text_input, "Escribe el nombre exacto de la competencia para confirmar").set_value("Sumo")
        widget(at.checkbox, "Entiendo que esta acción elimina los datos indicados").check()
        widget(at.button, "Confirmar reinicio").click().run()
        self.assertFalse(at.exception)
        self.assertFalse(self.repo.read()[0].competitions["Sumo"].teams)

    def test_rename_persists_after_app_rerun_and_new_session(self):
        self.load_tournament()
        at = self.app(True)
        self.page(at, "Equipos")
        widget(at.text_input, "Nombre").set_value("Swampy")
        widget(at.button, "Guardar equipo").click().run()
        self.assertFalse(at.exception)
        at.run()
        self.assertEqual(self.repo.read()[0].competitions["Sumo"].teams[0].nombre_equipo, "Swampy")
        second = self.app()
        self.page(second, "Equipos")
        self.assertIn("Swampy", second.dataframe[0].value["nombre_equipo"].tolist())
