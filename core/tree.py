"""Árbol simétrico de avance; la vista libre no inventa emparejamientos."""
from html import escape
from core.eliminatorias import FASES, ORDEN_FASES, fase_para, partidos_fase
from core.publication import LABELS, podium


def round_entries(c, phase):
    if c.config.sistema == "Libre":
        return list(c.rounds.get(phase, {}).items())
    return [(tid, "Pendiente" if not m.ganador else "Clasificado" if m.ganador == tid else "Eliminado")
            for m in partidos_fase(c, phase) for tid in (m.equipo_1, m.equipo_2) if tid]


def tree_phases(c):
    return ORDEN_FASES[ORDEN_FASES.index(fase_para(c.config.cupos_clasificados)):]


def tree_svg(c, start):
    stages = tree_phases(c)
    stages = stages[stages.index(start):]
    half = next(n for n, phase in FASES.items() if phase == start) // 2
    height = max(460, half * 66 + 110)
    step, card_width = 234, 204
    center = len(stages) * step + 126
    width = center * 2
    middle = height / 2 + 30
    shapes, links = [], []
    for side in (-1, 1):
        previous = None
        for column, phase in enumerate(stages):
            capacity = next(n for n, label in FASES.items() if label == phase) // 2
            x = 22 + column * step if side == -1 else width - 22 - column * step - card_width
            entries = round_entries(c, phase)
            entries = entries[:capacity] if side == -1 else entries[capacity:capacity*2]
            ys = [110 + (height-145) * (i+.5)/capacity for i in range(capacity)]
            shapes.append(f'<text x="{x+card_width/2}" y="62" text-anchor="middle" class="stage">{escape(LABELS[phase])}</text>')
            for index, y in enumerate(ys):
                tid, status = entries[index] if index < len(entries) else ("", "Pendiente")
                name = c.name(tid) if tid else "Por definir"
                label = name if len(name) <= 25 else name[:24] + "…"
                style = "winner" if status == "Clasificado" else "out" if status == "Eliminado" else "waiting" if not tid else "entry"
                status_label = "Clasifica" if status == "Clasificado" else "No clasifica" if status == "Eliminado" else "Pendiente" if tid else ""
                shapes.append(f'<g><title>{escape(name)} · {status_label}</title><rect x="{x}" y="{y-24}" width="{card_width}" height="48" rx="9" class="{style}"/>'
                              f'<text x="{x+12}" y="{y-3}" class="name">{escape(label)}</text><text x="{x+12}" y="{y+14}" class="status">{status_label}</text></g>')
            if previous:
                px, pys = previous
                edge = px + card_width if side == -1 else px
                incoming = x if side == -1 else x + card_width
                trunk = (edge + incoming) / 2
                # Conecta conjuntos de participantes: no asigna rivales ni ramas falsas.
                for y in pys:
                    links.append(f'<path d="M {edge} {y} H {trunk}"/>')
                for y in ys:
                    links.append(f'<path d="M {trunk} {y} H {incoming}"/>')
                links.append(f'<path d="M {trunk} {min(pys+ys)} V {max(pys+ys)}"/>')
            previous = x, ys
        px, ys = previous
        edge = px + card_width if side == -1 else px
        target = center - 90 if side == -1 else center + 90
        for y in ys:
            links.append(f'<path d="M {edge} {y} H {(edge+target)/2} V {middle} H {target}"/>')
    first = podium(c)[1]
    champion_name = c.name(first) if first else "Campeón por definir"
    short = champion_name if len(champion_name) <= 22 else champion_name[:21] + "…"
    shapes.append(f'<g><title>{escape(champion_name)}</title><rect x="{center-90}" y="{middle-72}" width="180" height="144" rx="18" class="trophy"/>'
                  f'<text x="{center}" y="{middle-24}" text-anchor="middle" font-size="38">🏆</text><text x="{center}" y="{middle+10}" text-anchor="middle" class="stage">CAMPEÓN</text>'
                  f'<text x="{center}" y="{middle+38}" text-anchor="middle" class="name">{escape(short)}</text></g>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Ruta al campeonato de {escape(c.config.competencia, quote=True)}" viewBox="0 0 {width} {height}">' + '''<style>
    text{font-family:Arial,sans-serif;fill:#173B3D}.stage{font-size:16px;font-weight:700;fill:#0D9648}.name{font-size:14px}.status{font-size:11px;fill:#647c81}
    rect{stroke-width:1.5}.entry{fill:white;stroke:#00A99D}.winner{fill:#e2f6ea;stroke:#0D9648}.out{fill:#eef1f0;stroke:#ccd6d3}.waiting{fill:#f9fbfa;stroke:#ccd6d3;stroke-dasharray:4 3}.trophy{fill:#e2f6ea;stroke:#0D9648}
    path{stroke:#9FCF67;stroke-width:2;fill:none}
    </style>''' + '<g>' + ''.join(links) + '</g>' + ''.join(shapes) + '</svg>'
