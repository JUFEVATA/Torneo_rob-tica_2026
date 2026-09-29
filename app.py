"""Punto de entrada: streamlit run app.py"""
import os
import pandas as pd
import streamlit as st

from components import admin, clasificados, configuracion, eliminatorias, equipos, grupos, participantes
from components.layout import bracket, champion, group_cards, hero, inject_style, metrics
from core.models import ValidationError
from services.runtime import admin_password, is_admin, login, read_state
from services.serialization import encode
from utils.helpers import csv_seguro

st.set_page_config(page_title="Torneos de robótica · STEM 2026", page_icon="🤖", layout="wide")
inject_style()


def configured():
    try:
        return bool(st.secrets.get("google_sheet", {}).get("sheet_id")) and "gcp_service_account" in st.secrets
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return False


mode = "demo" if os.environ.get("ROBOTICA_DEMO") == "1" or st.session_state.get("demo") else "sheets"
if mode == "sheets" and not configured():
    st.title("Torneos de robótica")
    st.info("La conexión todavía no está configurada. Sigue README.md y agrega google_sheet, gcp_service_account y admin en los Secrets de Streamlit.")
    if st.button("Explorar demostración", type="primary"):
        st.session_state.demo = True
        st.rerun()
    st.caption("La demostración usa datos ficticios y un archivo local separado. Para editarla, configura también admin.password en st.secrets.")
    st.stop()

with st.sidebar:
    st.markdown('<div class="brand">Torneos de robótica</div><div class="eyebrow" style="color:#FFFFFF;margin-top:8px">EQUIPO STEM 2026</div>', unsafe_allow_html=True)
    st.divider()
    if mode == "demo":
        st.caption("DEMOSTRACIÓN · DATOS LOCALES")
    st.caption("COMPETENCIA")
    try:
        initial_state, _ = read_state(mode)
    except ValidationError as error:
        st.error(str(error))
        st.info("Revisa los datos manuales en Sheets según README.md y pulsa Actualizar.")
        if st.button("Actualizar"):
            read_state.clear()
            st.rerun()
        st.stop()
    except Exception:
        st.error("No fue posible leer el torneo. Revisa el ID, las credenciales, la API habilitada y el permiso de editor del Service Account.")
        if st.button("Reintentar conexión"):
            read_state.clear()
            st.rerun()
        st.stop()
    options = list(initial_state.competitions)
    selected = st.selectbox("Competencia activa", options, label_visibility="collapsed") if options else None
    st.caption("TORNEO")
    pages = ["Inicio", "Participantes actuales", "Historial", "Grupos", "Clasificados", "Eliminatorias", "Cuadro", "Resultados"]
    if is_admin():
        pages += ["Configuración", "Equipos", "Administración"]
    page = st.radio("Navegación", pages, label_visibility="collapsed")
    st.divider()
    if is_admin():
        st.caption("● MODO ADMINISTRADOR")
        if st.button("Cerrar sesión"):
            st.session_state.pop("admin_signature", None)
            st.rerun()
    else:
        st.caption("◉ MODO PÚBLICO · SOLO LECTURA")
        with st.expander("Acceso administrador"):
            if not admin_password():
                st.caption("Configura admin.password en Secrets para habilitar el acceso.")
            with st.form("login", clear_on_submit=True):
                password = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Entrar"):
                    error = login(password)
                    if error:
                        st.error(error)
                    else:
                        st.rerun()
    if st.button("↻ Actualizar datos"):
        read_state.clear()
        st.rerun()
    st.caption("Actualización pública cada 10 segundos.")

if mode == "demo":
    st.info("Estás explorando una demostración. Los cambios se guardan localmente; conecta Google Sheets para el torneo real.")
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))
if "flash_error" in st.session_state:
    st.warning(st.session_state.pop("flash_error"))


@st.fragment(run_every="10s")
def content():
    try:
        state, revision = read_state(mode)
    except ValidationError as error:
        st.error(str(error))
        return
    except Exception:
        st.error("No se pudo actualizar Google Sheets. Usa Actualizar datos para volver a intentar.")
        return
    if list(state.competitions) != options:
        st.rerun()  # mantiene actualizado el selector al crear otra competencia
    c = state.competitions.get(selected)
    editable = is_admin()
    if page == "Configuración" or not c:
        if editable:
            configuracion.render(state, c, mode, revision, True)
        else:
            st.info("No hay competencias publicadas.")
        return
    st.markdown('<div class="eyebrow">CENTRO DE COMPETENCIA / ' + page.upper() + '</div>', unsafe_allow_html=True)
    if page == "Inicio":
        st.title("Torneos de robótica")
        hero(c)
        metrics(c)
        st.caption(f"Fase actual: {c.config.fase_actual}")
        champion(c)
        st.markdown('<div class="section-label">DISTRIBUCIÓN DEL TORNEO</div>', unsafe_allow_html=True)
        st.subheader("Grupos en competencia")
        group_cards(c)
    elif page == "Participantes actuales":
        participantes.actuales(c)
    elif page == "Historial":
        participantes.historial(c)
    elif page == "Equipos":
        equipos.render(c, mode, revision, editable)
    elif page == "Grupos":
        grupos.render(c, mode, revision, editable)
    elif page == "Clasificados":
        clasificados.render(c, mode, revision, editable)
    elif page == "Eliminatorias":
        eliminatorias.render(c, mode, revision, editable)
    elif page == "Cuadro":
        st.header("Cuadro del torneo")
        bracket(c)
    elif page == "Resultados":
        st.header("Resultados")
        champion(c)
        if c.matches:
            frame = pd.DataFrame([{"Ronda": m.fase, "Partido": m.numero_partido,
                                   "Equipo 1": c.name(m.equipo_1), "Equipo 2": c.name(m.equipo_2),
                                   "Ganador": c.name(m.ganador) if m.ganador else "", "Estado": m.estado}
                                  for m in c.matches])
            st.dataframe(frame, hide_index=True, width="stretch")
            st.download_button("Descargar resultados CSV", csv_seguro(frame), "resultados.csv", "text/csv")
        else:
            st.info("Todavía no hay partidos registrados.")
    elif page == "Administración":
        admin.render(c, mode, revision, editable)


content()
