"""Datos ficticios; nunca se conectan a la hoja de producción."""
from core.models import Config
from core.tournament import agregar_equipos, crear_competencia, iniciar_grupos, clasificar


def seed(repo):
    state, revision = repo.read()
    if state.competitions:
        return
    def populate(s):
        crear_competencia(s, Config("Seguidor de línea", 32, 6, 87, 16))
        c = s.competitions["Seguidor de línea"]
        names = ["Swampy", "Hercules", "Neobots", "Aquiles", "Bytebots", "Duracell", "OmegaTech", "Volt",
                 "Circuit Breakers", "Atlas", "Nova", "Titan", "Vector", "Edison", "Pixel", "Nébula",
                 "Bolt", "Cobalto", "Nexus", "Quark", "Rayo", "Delta", "Fénix", "Pulsar",
                 "Quantum", "Orbit", "Tesla", "Flux", "Photon", "Axon", "Rover", "Apolo"]
        agregar_equipos(c, names, [3] * 23 + [2] * 9)
        iniciar_grupos(c)
        for team in c.teams[:12]:
            clasificar(c, team.id_equipo, "Clasificado")
        crear_competencia(s, Config("Sumo", 16, 4, 48, 8))
        crear_competencia(s, Config("Robot Edison", 8, 2, 24, 4))
    repo.transact(revision, populate)
