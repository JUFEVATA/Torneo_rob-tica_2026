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

    def name(self, team_id: str) -> str:
        return next((t.nombre_equipo for t in self.teams if t.id_equipo == team_id), "Por definir")


@dataclass
class State:
    competitions: dict[str, Competition] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "State":
        return cls({key: Competition(Config(**v["config"]),
                                    [Team(**t) for t in v["teams"]],
                                    [Match(**m) for m in v["matches"]])
                    for key, v in data["competitions"].items()})
