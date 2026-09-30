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
            widget(at.button, "EQUIPO STEM 2026").click().run()
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
        self.assertFalse({"Configuración", "Equipos", "Administración"}.intersection(widget(at.radio, "Navegación").options))
        self.assertEqual(widget(at.radio, "Navegación").options, ["Inicio", "Fases", "Podio"])
        self.assertFalse(any(w.label == "Competencia activa" for w in at.selectbox))
        for page in ["Inicio", "Fases", "Podio"]:
            self.page(at, page)
            self.assertFalse(forbidden.intersection(b.label for b in at.button))
            self.assertFalse(at.dataframe)
            self.assertFalse(at.get("download_button"))
            self.assertFalse(at.text_input)
            self.assertFalse(at.expander)
            self.assertFalse(any("MODO PÚBLICO" in w.value or "Actualización pública" in w.value for w in at.caption))

    def test_admin_all_pages(self):
        self.load_tournament()
        at = self.app(True)
        for page in ["Inicio", "Fases", "Podio", "Publicación", "Configuración", "Equipos", "Grupos", "Eliminatorias", "Historial", "Administración"]:
            self.page(at, page)

    def test_publish_stage_and_competition_shared_with_new_public_session(self):
        from tests.test_free_rounds import free_state
        from core.free_rounds import classify
        state,c=free_state()
        for t in c.teams[:2]: classify(c, "Grupos", t.id_equipo, "Clasificado")
        _,rev=self.repo.read();self.repo.transact(rev,lambda s:s.competitions.update(state.competitions))
        at=self.app(True);self.page(at,"Publicación")
        widget(at.selectbox,"Etapa visible en Inicio").set_value("Dieciseisavos")
        widget(at.button,"Publicar competencia y etapa").click().run()
        self.assertFalse(at.exception)
        public=self.app()
        self.assertFalse(public.dataframe)
        cards=" ".join(m.value for m in public.markdown)
        self.assertIn("group-card", cards)
        for t in c.teams[:2]: self.assertIn(t.nombre_equipo, cards)
        self.assertTrue(any(h.value=="16 avos" for h in public.header))
        self.assertFalse(any("Equipo 1" in m.value for m in public.markdown))

    def test_save_three_places_visible_to_public(self):
        self.load_tournament();at=self.app(True);self.page(at,"Podio")
        ids=[t.id_equipo for t in self.repo.read()[0].competitions["Sumo"].teams[:3]]
        for label,tid in zip(["Primer puesto","Segundo puesto","Tercer puesto"],ids):widget(at.selectbox,label).set_value(tid)
        widget(at.button,"Guardar podio").click().run();self.assertFalse(at.exception)
        public=self.app();self.page(public,"Podio")
        html=" ".join(m.value for m in public.markdown)
        for label in ["1.º puesto","2.º puesto","3.º puesto","Equipo 1","Equipo 2","Equipo 3"]:self.assertIn(label,html)
        self.assertFalse(any(b.label=="Guardar podio" for b in public.button))

    def test_delete_and_restore_last_competition_from_admin(self):
        self.load_tournament();at=self.app(True);self.page(at,"Administración")
        widget(at.button,"Eliminar competencia").click().run()
        self.assertTrue(self.repo.read()[0].competitions)
        widget(at.text_input,"Nombre de la competencia que vas a eliminar").set_value("Sumo")
        widget(at.button,"Eliminar competencia").click().run();self.assertFalse(at.exception)
        self.assertFalse(self.repo.read()[0].competitions)
        self.assertEqual(len(self.repo.read()[0].archived),1)
        widget(at.button,"Restaurar competencia").click().run();self.assertFalse(at.exception)
        self.assertEqual(len(self.repo.read()[0].competitions["Sumo"].teams),8)

    def test_logout_from_admin_page_returns_to_public_home(self):
        self.load_tournament();at=self.app(True);self.page(at,"Configuración")
        widget(at.button,"Cerrar sesión").click().run();self.assertFalse(at.exception)
        self.assertEqual(widget(at.radio,"Navegación").options,["Inicio","Fases","Podio"])
        self.assertFalse(at.text_input)
        self.assertFalse(any(w.label=="Competencia activa" for w in at.selectbox))

    def test_free_public_and_admin_pages_and_save(self):
        from tests.test_free_rounds import free_state
        from core.free_rounds import classify
        state,c=free_state()
        for team in c.teams[:32]: classify(c,'Grupos',team.id_equipo,'Clasificado')
        _,rev=self.repo.read();self.repo.transact(rev,lambda s:s.competitions.update(state.competitions))
        at=self.app()
        for name in ['Inicio','Fases','Podio']:
            self.page(at,name)
            self.assertFalse(any(b.label=='Guardar clasificación' for b in at.button))
        at=self.app(True)
        for name in ['Configuración','Equipos','Grupos','Eliminatorias','Podio','Publicación','Administración']:
            self.page(at,name)
        self.page(at,'Eliminatorias')
        for team in c.teams[:2]:widget(at.selectbox,team.nombre_equipo).set_value('Clasifica')
        widget(at.button,'Guardar clasificación').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(len(self.repo.read()[0].competitions['Sumo'].rounds['Octavos']),2)

    def test_wrong_password_cannot_edit(self):
        self.load_tournament()
        at = self.app()
        self.assertFalse(at.text_input)
        widget(at.button, "EQUIPO STEM 2026").click().run()
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
        self.page(at, "Eliminatorias")
        widget(at.button, "GENERAR ELIMINATORIAS").click().run()
        self.page(at, "Eliminatorias")
        for _ in range(7):
            buttons = [b for b in at.button if b.label.endswith(" gana") and not b.disabled]
            self.assertTrue(buttons)
            buttons[0].click().run()
            self.assertFalse(at.exception)
        self.assertTrue(self.repo.read()[0].competitions["Sumo"].config.campeon)
        public = self.app()
        self.page(public, "Podio")
        self.assertTrue(any("1.º puesto" in m.value for m in public.markdown))
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
        self.page(second, "Inicio")
        self.assertTrue(any("Swampy" in m.value for m in second.markdown))

    def test_admin_imports_complete_roster_and_public_history(self):
        at = self.app(True)
        example = (APP.parent / "examples" / "sumo2026.txt").read_text()
        widget(at.text_area, "Lista completa").set_value(example)
        widget(at.button, "Importar grupos").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(len(self.repo.read()[0].competitions["Sumo"].teams),85)
        public = self.app()
        self.assertEqual(widget(public.radio, "Navegación").options, ["Inicio", "Fases", "Podio"])
        self.page(at,"Historial")
        self.assertEqual(len(at.dataframe[0].value),85)

    def test_admin_group_dropdown_persists(self):
        self.load_tournament()
        at=self.app(True)
        self.page(at,"Grupos")
        team=self.repo.read()[0].competitions["Sumo"].teams[0]
        widget(at.selectbox,"Estado de " + team.nombre_equipo).set_value("Pendiente").run()
        self.assertFalse(at.exception)
        self.assertEqual(self.repo.read()[0].competitions["Sumo"].teams[0].estado,"Pendiente")

    def test_admin_resize_form_keeps_reserved_names(self):
        from tests.test_sheet_flow import imported
        _,rev=self.repo.read()
        state=imported()
        self.repo.transact(rev,lambda s:s.competitions.update(state.competitions))
        at=self.app(True);self.page(at,"Configuración")
        widget(at.number_input,"Equipos inscritos en competencia").set_value(54)
        widget(at.number_input,"Cantidad de bloques / grupos").set_value(8)
        widget(at.button,"Aplicar distribución").click().run()
        self.assertFalse(at.exception)
        c=self.repo.read()[0].competitions['Sumo']
        self.assertEqual(len(c.teams),54);self.assertEqual(len(c.reserve),31)
        self.page(at,"Equipos")
        self.assertTrue(any(len(frame.value)==31 for frame in at.dataframe))

    def test_invalid_sheet_notice_keeps_public_navigation_available(self):
        self.load_tournament()
        state,rev=self.repo.read();state.sync_error="Partido con dos ganadores; revisar en Sheets."
        with patch("services.runtime.read_state",return_value=(state,rev)):
            at=self.app()
            self.assertTrue(at.warning)
            self.assertFalse(at.error)
            self.page(at,"Inicio")
            self.assertTrue(any("Equipo 1" in m.value for m in at.markdown))
