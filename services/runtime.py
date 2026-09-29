"""Puente Streamlit: autenticación, caché compartida y escrituras autorizadas."""
from hashlib import sha256
import hmac
from pathlib import Path
from threading import Lock
import time

import streamlit as st

from core.models import ConflictError, ValidationError
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
    if mode == "demo":
        from services.demo import seed
        repo = LocalRepository(Path(__file__).resolve().parents[1] / ".demo" / "torneo.json")
        seed(repo)
        return repo
    return conectar_google_sheets(st.secrets["gcp_service_account"], st.secrets["google_sheet"]["sheet_id"])


@st.cache_data(ttl=10, show_spinner=False)
def read_state(mode):
    return get_repository(mode).read()


def execute(mode, revision, operation, message="Cambios guardados."):
    if not is_admin():
        st.error("Inicia sesión como administrador para modificar el torneo.")
        return
    try:
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
    st.rerun()
