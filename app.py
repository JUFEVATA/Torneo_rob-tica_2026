"""Punto de entrada: streamlit run app.py"""
import os
from html import escape
import streamlit as st

from components import admin, clasificados, configuracion, eliminatorias, equipos, grupos, participantes, rondas_libres, publico, publicacion
from components.layout import inject_style
from core.models import ValidationError
from core.publication import PUBLIC_PAGES, public_name
from services.runtime import admin_password, is_admin, login, read_state, get_repository, connection_error

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
    st.markdown('<div class="brand">Torneos de robótica</div>', unsafe_allow_html=True)
    if is_admin():
        st.markdown('<div class="eyebrow" style="color:#FFFFFF;margin-top:8px">EQUIPO STEM 2026</div>', unsafe_allow_html=True)
    else:
        if st.button("EQUIPO STEM 2026", key="admin_access", type="tertiary"):
            st.session_state.admin_login_open = not st.session_state.get("admin_login_open", False)
        if st.session_state.get("admin_login_open"):
            if not admin_password():
                st.caption("Configura admin.password en Secrets para habilitar el acceso.")
            with st.form("login", clear_on_submit=True):
                password = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Entrar", type="primary"):
                    error = login(password)
                    if error:
                        st.error(error)
                    else:
                        st.session_state.admin_login_open = False
                        st.rerun()
    st.divider()
    if mode == "demo":
        st.caption("DEMOSTRACIÓN · DATOS LOCALES")
    try:
        initial_state, _ = read_state(mode)
    except ValidationError as error:
        st.error(str(error))
        st.info("Revisa los datos manuales en Sheets según README.md y pulsa Actualizar.")
        if st.button("Actualizar"):
            read_state.clear()
            get_repository.clear()
            st.rerun()
        st.stop()
    except Exception as error:
        st.error(connection_error(error))
        if st.button("Reintentar conexión"):
            read_state.clear()
            get_repository.clear()
            st.rerun()
        st.stop()
    options = list(initial_state.competitions)
    editable_at_start = is_admin()
    if editable_at_start:
        st.caption("COMPETENCIA")
        selected = st.selectbox("Competencia activa", options, label_visibility="collapsed") if options else None
    else:
        selected = public_name(initial_state)
        if selected:
            st.markdown(f'<div class="competition-name">{escape(selected)}</div>', unsafe_allow_html=True)
    pages = PUBLIC_PAGES + (["Publicación", "Configuración", "Equipos", "Grupos", "Eliminatorias", "Historial", "Administración"] if editable_at_start else [])
    page = st.radio("Navegación", pages, label_visibility="collapsed", key="admin_navigation" if editable_at_start else "public_navigation")
    st.divider()
    if is_admin():
        st.caption("● MODO ADMINISTRADOR")
        if st.button("Cerrar sesión"):
            st.session_state.pop("admin_signature", None)
            st.session_state.admin_login_open = False
            st.rerun()
    if st.button("↻ Actualizar datos"):
        read_state.clear()
        st.rerun()

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
    except Exception as error:
        st.error(connection_error(error))
        return
    editable = is_admin()
    if list(state.competitions) != options or editable != editable_at_start or (not editable and public_name(state) != selected):
        st.rerun()
    c = state.competitions.get(selected if editable else public_name(state))
    if getattr(state, "sync_error", ""):
        st.warning("Hay decisiones en la hoja pendientes de revisión. Se muestran los últimos resultados validados.")
        if editable:
            st.error(state.sync_error)
    if page == "Administración" and editable:
        admin.render(state, c, mode, revision, True)
        return
    if page == "Configuración" or not c:
        if editable:
            configuracion.render(state, c, mode, revision, True)
        else:
            st.info("No hay competencias publicadas.")
        return
    st.markdown('<div class="eyebrow">CENTRO DE COMPETENCIA / ' + page.upper() + '</div>', unsafe_allow_html=True)
    if page == "Inicio":
        publico.home(c)
    elif page == "Fases":
        publico.render_tree(c)
    elif page == "Podio":
        publico.render_podium(c)
        if editable:
            publicacion.edit_podium(c, mode, revision)
    elif page == "Publicación" and editable:
        publicacion.render(state, c, mode, revision)
    elif page == "Historial":
        participantes.historial(c)
    elif page == "Equipos":
        equipos.render(c, mode, revision, editable)
    elif page == "Grupos":
        grupos.render(c, mode, revision, editable)
    elif c.config.sistema == "Libre" and page == "Eliminatorias":
        rondas_libres.render(c, mode, revision, editable)
    elif page == "Eliminatorias":
        if not c.matches:
            clasificados.render(c, mode, revision, editable)
        else:
            eliminatorias.render(c, mode, revision, editable)


content()
