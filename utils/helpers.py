import csv
import io
import pandas as pd

from core.models import ValidationError
from services.serialization import entero


def importar_csv(data: bytes) -> tuple[list[str], list[int]]:
    if len(data) > 2_000_000:
        raise ValidationError("El CSV no debe superar 2 MB.")
    try:
        text = data.decode("utf-8-sig")
        delimiter = ";" if ";" in text.splitlines()[0] else ","
        frame = pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str, keep_default_na=False)
    except (UnicodeError, ValueError, IndexError, pd.errors.ParserError):
        raise ValidationError("No se pudo leer el CSV. Usa UTF-8 y el encabezado nombre_equipo.") from None
    if "nombre_equipo" not in frame:
        raise ValidationError("El CSV debe incluir una columna nombre_equipo.")
    names = frame["nombre_equipo"].tolist()
    participants = [entero(v or 0) for v in frame["numero_participantes"]] if "numero_participantes" in frame else [0] * len(names)
    return names, participants


def csv_seguro(frame: pd.DataFrame) -> bytes:
    # Neutraliza fórmulas cuando se abre el CSV en Excel/Sheets.
    def safe(value):
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value
    return frame.map(safe).to_csv(index=False, quoting=csv.QUOTE_MINIMAL).encode("utf-8-sig")
