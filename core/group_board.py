"""Tablero de tarjetas: cantidades sincronizadas al editar los selectores."""
from copy import deepcopy
from core.models import Team, ValidationError, new_id
from core.grupos import distribuir, generar_grupos, nombre_columna
from core.tournament import normalizar

MARKER = 'TABLERO DE GRUPOS'
CARDS_PER_ROW = 6
STRIDE = 4  # nombre, desplegable, ID oculto, espacio
PUBLIC = {'Pendiente':'Pendiente', 'Clasificado':'Clasifica', 'Eliminado':'No clasifica'}


def value(rows, r, c, default=''):
    return rows[r][c] if r<len(rows) and c<len(rows[r]) else default


def sections(rows):
    return [(i,str(row[0])[len('Competencia: '):]) for i,row in enumerate(rows)
            if row and str(row[0]).startswith('Competencia: ')]


def board_rows(state):
    rows = [[MARKER],[]]
    for name,c in state.competitions.items():
        if not c.config.torneo_iniciado:
            continue
        locked = bool(c.matches) or any(t.estado != 'Pendiente' for t in c.teams)
        rows += [[f'Competencia: {name}'],[c.config.titulo],
                 ['Equipos inscritos',len(c.teams),'','','Bloques / grupos',c.config.numero_grupos,'','','Cupos clasifican',c.config.cupos_clasificados,'','','Actualización','Automática'],
                 [f'{len(c.teams)} equipos · {c.config.numero_grupos} grupos · {len(c.reserve)} en reserva · Fase: {c.config.fase_actual}'],
                 ['Cambia Bloques / grupos: conserva equipos y resultados. Total y cupos cerrados durante la competencia.' if locked else 'Cambia las cantidades: las tarjetas se actualizan al sincronizar. No necesitas marcar una casilla.'],[]]
        for start in range(0,c.config.numero_grupos,CARDS_PER_ROW):
            groups=[nombre_columna(i+1) for i in range(start,min(start+CARDS_PER_ROW,c.config.numero_grupos))]
            members=[[t for t in c.teams if t.grupo==g] for g in groups]
            band=[['']*(len(groups)*STRIDE) for _ in range(max(map(len,members))+1)]
            for k,(g,teams) in enumerate(zip(groups,members)):
                col=k*STRIDE
                band[0][col:col+3]=[f'Grupo {g}',f'{len(teams):02d}',f'group:{g}']
                for r,t in enumerate(teams,1):
                    band[r][col:col+3]=[t.nombre_equipo,PUBLIC[t.estado],t.id_equipo]
            rows += band+[[],[]]
    return rows


def preserve_drafts(projected, original):
    # Compatibilidad con los llamadores anteriores: ahora las cantidades se aplican
    # automáticamente y la proyección refleja el último estado validado.
    return projected


def resize_groups(c,total,groups,cupos,shuffle=False):
    for label,n in [('Equipos',total),('Grupos',groups),('Cupos',cupos)]:
        if type(n) is not int or not 1<=n<=4096:
            raise ValidationError(f'{label}: escribe un entero entre 1 y 4096.')
    if c.config.sistema == 'Tiempos' and total >= 2 and cupos > total:
        cupos = max(n for n in (2,4,8,16,32,64) if n <= total)
    if total<2 or groups>total or cupos not in (2,4,8,16,32,64) or cupos>total:
        raise ValidationError('Revisa las cantidades: al menos 2 equipos, grupos no superiores al total y cupos de 2, 4, 8, 16, 32 o 64 sin superar el total.')
    if c.matches or any(t.estado!='Pendiente' for t in c.teams):
        if total != len(c.teams) or cupos != c.config.cupos_clasificados:
            raise ValidationError('Durante la competencia puedes cambiar los grupos. Para cambiar inscritos o cupos, reinicia la fase como administrador.')
        generar_grupos(c.teams,groups,shuffle)
        c.config.numero_grupos=groups
        c.config.equipos_por_grupo=', '.join(map(str,distribuir(total,groups)))
        return
    all_teams=deepcopy(c.teams+c.reserve)
    names={normalizar(t.nombre_equipo) for t in all_teams}
    index=1
    while len(all_teams)<total:
        name=f'Equipo nuevo {index}'
        index+=1
        if normalizar(name) in names:
            continue
        all_teams.append(Team(new_id(),name,c.config.competencia))
        names.add(normalizar(name))
    c.teams,c.reserve=all_teams[:total],all_teams[total:]
    for t in c.reserve:
        t.grupo,t.estado,t.clasificado='','Pendiente',False
    c.config.numero_equipos,c.config.numero_grupos,c.config.cupos_clasificados=total,groups,cupos
    generar_grupos(c.teams,groups,shuffle)
    c.config.equipos_por_grupo=', '.join(map(str,distribuir(total,groups)))
    c.config.metodo_grupos='Sorteo aleatorio' if shuffle else 'Orden original'
    c.config.torneo_iniciado=True
    c.config.fase_actual='Grupos'
    c.config.campeon=''
    if c.config.sistema == 'Tiempos':
        valid_ids = {t.id_equipo for t in c.teams}
        for key in ('puesto_1', 'puesto_2', 'puesto_3'):
            if getattr(c.config, key) not in valid_ids: setattr(c.config, key, '')
        from core.line_racing import reconcile
        reconcile(c)


def parse_board(state,rows):
    """Convierte tarjetas en el formato de importación; separa controles pendientes."""
    roster_rows, actions = [], {}
    starts=sections(rows)
    expected={name for name,c in state.competitions.items() if c.config.torneo_iniciado}
    if len(starts)!=len(expected) or {name for _,name in starts}!=expected:
        raise ValidationError('No borres ni cambies los encabezados de competencia del tablero. Importa listas nuevas desde Configuración.')
    for pos,(start,name) in enumerate(starts):
        c=state.competitions[name]
        end=starts[pos+1][0] if pos+1<len(starts) else len(rows)
        roster_rows += [['TORNEOS DE ROBÓTICA'],[value(rows,start+1,0)],['Competencia: '+name],
                        ['Fecha: '+c.config.fecha],[f'Participantes: {c.config.numero_participantes} | Grupos: {c.config.numero_grupos}']]
        groups_seen=set()
        for r in range(start+6,end):
            for col in range(0,CARDS_PER_ROW*STRIDE,STRIDE):
                marker=str(value(rows,r,col+2))
                if not marker.startswith('group:'):
                    continue
                group=marker.split(':',1)[1]
                if group in groups_seen:
                    raise ValidationError('Hay un grupo duplicado en el tablero.')
                groups_seen.add(group)
                roster_rows.append(['Grupo '+group])
                rr=r+1
                while rr<end and value(rows,rr,col+2) and not str(value(rows,rr,col+2)).startswith('group:'):
                    roster_rows.append(['• '+str(value(rows,rr,col)),value(rows,rr,col+1),value(rows,rr,col+2)])
                    rr+=1
        if groups_seen!={nombre_columna(i+1) for i in range(c.config.numero_grupos)}:
            raise ValidationError('Faltan tarjetas de grupos. No borres sus encabezados ni IDs ocultos.')
        vals=[]
        for col in (1,5,9):
            raw=value(rows,start+2,col)
            try:
                n=int(str(raw))
            except (ValueError,TypeError):
                raise ValidationError('Las cantidades deben ser números enteros.') from None
            vals.append(n)
        # Al reducir inscritos antes de iniciar, adapta los cupos si ya no caben.
        if vals[0] != len(c.teams) and vals[2] == c.config.cupos_clasificados and 2 <= vals[0] < vals[2]:
            vals[2]=max(n for n in (2,4,8,16,32,64) if n<=vals[0])
        if vals != [len(c.teams),c.config.numero_grupos,c.config.cupos_clasificados]:
            actions[name]=vals
    return roster_rows,actions
