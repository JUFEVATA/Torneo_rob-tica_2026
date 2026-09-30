"""Clasificación libre: cada seleccionado aparece inmediatamente en la fase siguiente."""
from copy import deepcopy
from core.models import ValidationError
from core.eliminatorias import FASES,ORDEN_FASES,fase_para


def phases(c):
    return ORDEN_FASES[ORDEN_FASES.index(fase_para(c.config.cupos_clasificados)):]


def reconcile(c):
    incoming=[t.id_equipo for t in c.teams if t.clasificado]
    previous=c.rounds
    result={}
    for phase in phases(c):
        if not incoming: break
        old=previous.get(phase,{})
        entries={tid:old.get(tid,'Pendiente') for tid in incoming}
        if any(s not in ('Pendiente','Clasificado','Eliminado') for s in entries.values()):
            raise ValidationError('Estado inválido en clasificación libre.')
        capacity=next(n for n,f in FASES.items() if f==phase)//2
        incoming=[tid for tid,s in entries.items() if s=='Clasificado']
        if len(incoming)>capacity:
            raise ValidationError(f'{phase}: pueden avanzar como máximo {capacity} equipos; hay {len(incoming)} seleccionados.')
        result[phase]=entries
    c.rounds=result
    final=[tid for tid,s in result.get('Final',{}).items() if s=='Clasificado']
    c.config.campeon=final[0] if final else ''
    c.config.fase_actual='Finalizado' if final else next(reversed(result)) if result else 'Grupos' if c.config.torneo_iniciado else 'Inscripción'


def validate(c):
    if c.matches:
        raise ValidationError('Una competencia libre no utiliza cruces por parejas.')
    expected=deepcopy(c);reconcile(expected)
    if expected.rounds!=c.rounds or expected.config.fase_actual!=c.config.fase_actual or expected.config.campeon!=c.config.campeon:
        raise ValidationError('Las rondas libres no coinciden con los clasificados de la fase anterior.')


def classify(c,phase,tid,status):
    if phase=='Grupos':
        team=next((t for t in c.teams if t.id_equipo==tid),None)
        if team is None:raise ValidationError('El equipo no existe.')
        if status not in ('Pendiente','Clasificado','Eliminado'):raise ValidationError('Estado inválido.')
        if status=='Clasificado' and not team.clasificado and sum(t.clasificado for t in c.teams)>=c.config.cupos_clasificados:
            raise ValidationError('Ya están completos los cupos de grupos.')
        team.estado,team.clasificado=status,status=='Clasificado'
    else:
        if tid not in c.rounds.get(phase,{}):raise ValidationError('El equipo no participa en esta fase.')
        c.rounds[phase][tid]=status
    reconcile(c)


def active(c):
    if c.config.campeon:return {c.config.campeon:'Campeón'}
    filled=sum(t.clasificado for t in c.teams)==c.config.cupos_clasificados
    current={t.id_equipo:'Grupos' for t in c.teams if t.estado!='Eliminado' and (not filled or t.clasificado)}
    for phase in phases(c):
        entries=c.rounds.get(phase,{})
        full=sum(s=='Clasificado' for s in entries.values())==next(n for n,f in FASES.items() if f==phase)//2
        for tid,status in entries.items():
            if status=='Eliminado' or (full and status!='Clasificado'):current.pop(tid,None)
            else:current[tid]=phase
    return current


def reset(c,scope):
    if scope=='Competencia completa':
        c.teams.clear();c.reserve.clear();c.rounds.clear();c.config.torneo_iniciado=False
    elif scope=='Eliminatorias':
        c.rounds.clear()
    elif scope=='Fase actual':
        if c.rounds:
            phase='Final' if c.config.campeon else c.config.fase_actual
            c.rounds[phase]={tid:'Pendiente' for tid in c.rounds[phase]}
        else:
            for t in c.teams:t.grupo,t.estado,t.clasificado='','Pendiente',False
            c.config.torneo_iniciado=False;c.config.equipos_por_grupo=''
    else:raise ValidationError('Alcance de reinicio inválido.')
    reconcile(c)
