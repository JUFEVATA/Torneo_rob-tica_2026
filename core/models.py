"""Modelo independiente de Streamlit y Google Sheets."""
from dataclasses import asdict, dataclass, field
from uuid import uuid4


class ValidationError(ValueError):
    pass


class ConflictError(ValidationError):
    pass


def new_id() -> str:
    return uuid4().hex


@dataclass
class Config:
    competencia: str
    numero_equipos: int
    numero_grupos: int
    numero_participantes: int = 0
    cupos_clasificados: int = 2
    fase_actual: str = "Inscripción"
    torneo_iniciado: bool = False
    equipos_por_grupo: str = ""
    campeon: str = ""
    metodo_grupos: str = "Orden original"
    titulo: str = "Equipo STEM 2026"
    fecha: str = ""
    sistema: str = "Enfrentamientos"
    etapa_publica: str = ""
    puesto_1: str = ""
    puesto_2: str = ""
    puesto_3: str = ""
    regla_fallos: str = "Por fase"


@dataclass
class Team:
    id_equipo: str
    nombre_equipo: str
    competencia: str
    grupo: str = ""
    clasificado: bool = False
    estado: str = "Pendiente"
    numero_participantes: int = 0


@dataclass
class Match:
    id_partido: str
    competencia: str
    fase: str
    numero_partido: int
    equipo_1: str = ""
    equipo_2: str = ""
    ganador: str = ""
    estado: str = "Pendiente"


@dataclass
class Competition:
    config: Config
    teams: list[Team] = field(default_factory=list)
    matches: list[Match] = field(default_factory=list)
    reserve: list[Team] = field(default_factory=list)
    rounds: dict[str, dict[str, str]] = field(default_factory=dict)
    timing: dict[str, dict[str, dict]] = field(default_factory=dict)
    closed_phases: list[str] = field(default_factory=list)

    def name(self, team_id: str) -> str:
        return next((t.nombre_equipo for t in self.teams if t.id_equipo == team_id), "Por definir")


@dataclass
class State:
    competitions: dict[str, Competition] = field(default_factory=dict)
    public_competition: str = ""
    archived: dict[str, Competition] = field(default_factory=dict)
    recovery_backups: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "State":
        def competition(v):
            return Competition(Config(**v["config"]), [Team(**t) for t in v["teams"]],
                               [Match(**m) for m in v["matches"]],
                               [Team(**t) for t in v.get("reserve", [])], v.get("rounds", {}),
                               v.get("timing", {}), v.get("closed_phases", []))
        return cls({key: competition(v) for key, v in data["competitions"].items()},
                   data.get("public_competition", ""),
                   {key: competition(v) for key, v in data.get("archived", {}).items()}, data.get("recovery_backups", {}))
