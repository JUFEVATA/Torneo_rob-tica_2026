"""Puente Streamlit: autenticación, caché compartida y escrituras autorizadas."""
from hashlib import sha256
import hmac
from pathlib import Path
from threading import Lock
import time

import streamlit as st

from core.models import ConflictError, ValidationError, State
from services.google_sheets import conectar_google_sheets
from services.repository import LocalRepository


def admin_password():
    try:
        return str(st.secrets.get("admin", {}).get("password", ""))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return ""


def is_admin():
    password = admin_password()
    return bool(password) and hmac.compare_digest(
        st.session_state.get("admin_signature", ""), sha256(password.encode()).hexdigest())


@st.cache_resource
def login_limiter():
    return {"attempts": [], "lock": Lock()}


def login(password):
    limiter = login_limiter()
    with limiter["lock"]:
        now = time.monotonic()
        limiter["attempts"] = [t for t in limiter["attempts"] if now - t < 60]
        if len(limiter["attempts"]) >= 10:
            return "Demasiados intentos. Espera un minuto antes de volver a intentar."
        expected = admin_password()
        if expected and hmac.compare_digest(password.encode(), expected.encode()):
            st.session_state.admin_signature = sha256(expected.encode()).hexdigest()
            limiter["attempts"].clear()
            return ""
        limiter["attempts"].append(now)
        return "Contraseña incorrecta o acceso administrador sin configurar."


@st.cache_resource
def get_repository(mode):
    # Schema v6: tiempos de seguidor de línea y recuperación con respaldo.
    if mode == "demo":
        from services.demo import seed
        repo = LocalRepository(Path(__file__).resolve().parents[1] / ".demo" / "torneo.json")
        seed(repo)
        return repo
    return conectar_google_sheets(st.secrets["gcp_service_account"], st.secrets["google_sheet"]["sheet_id"])


@st.cache_data(ttl=10, show_spinner=False)
def _read_data(mode):
    state, revision = get_repository(mode).read()
    # Solo datos básicos en caché: las clases pueden cambiar durante un despliegue.
    return state.to_dict(), revision, getattr(state, "sync_issues", {}), getattr(state, "sync_error", "")


def read_state(mode):
    data, revision, issues, error = _read_data(mode)
    state = State.from_dict(data)
    if issues:
        state.sync_issues = issues
    if error:
        state.sync_error = error
    return state, revision


read_state.clear = _read_data.clear


def execute(mode, revision, operation, message="Cambios guardados.", recovery=None, select_competition=None):
    if not is_admin():
        st.error("Inicia sesión como administrador para modificar el torneo.")
        return
    try:
        if recovery:
            get_repository(mode).recover(revision, *recovery)
        else:
            get_repository(mode).transact(revision, operation)
    except ConflictError as error:
        read_state.clear()
        st.session_state.flash_error = str(error)
        st.rerun()
    except ValidationError as error:
        st.error(str(error))
        return
    except Exception:
        # No revelar credenciales ni repetir una escritura de resultado incierto.
        read_state.clear()
        st.error("No se pudo confirmar la escritura. Actualiza para comprobar el estado antes de repetirla. Revisa la conexión y los permisos de Google Sheets.")
        return
    read_state.clear()
    st.session_state.flash = message
    if select_competition:
        st.session_state.pending_competition = " ".join(select_competition.split())
    st.rerun()


def connection_error(error):
    """Diagnóstico público limitado: nunca muestra claves ni el contenido de Secrets."""
    name = type(error).__name__
    response = getattr(error, 'response', None)
    code = getattr(response, 'status_code', None)
    if name in ('RefreshError', 'InvalidValue', 'MalformedError'):
        return 'Google no aceptó la cuenta de servicio. Revisa gcp_service_account en Secrets. (' + name + ')'
    if name in ('SpreadsheetNotFound', 'PermissionError') or code in (403, 404):
        return 'Revisa el ID, la API de Sheets y el permiso de editor de la cuenta de servicio. (' + name + ')'
    if code == 429:
        return 'Google limitó temporalmente las solicitudes. Espera un minuto y reintenta.'
    return 'No fue posible leer el torneo. Pulsa Reintentar conexión. Diagnóstico: ' + name + (f' HTTP {code}' if code else '')
