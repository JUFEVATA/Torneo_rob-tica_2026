"""Formato nativo de tarjetas para el tablero de Google Sheets."""
from core.group_board import CARDS_PER_ROW, STRIDE, sections, value
from core.podium_sheet import UNDEFINED


def color(hexcode):
    return dict(zip(('red','green','blue'),(int(hexcode[i:i+2],16)/255 for i in (1,3,5))))


def line_format_requests(sid, rows, height, width):
    """Tiempos como texto exacto, decisiones nativas y resultados derivados."""
    def area(r=0, end=None, col=0, last=10):
        result = {'sheetId': sid, 'startRowIndex': r, 'startColumnIndex': col, 'endColumnIndex': last}
        if end is not None: result['endRowIndex'] = end
        return result
    def paint(r, end, style):
        return {'repeatCell': {'range': area(r, end), 'cell': {'userEnteredFormat': style}, 'fields': 'userEnteredFormat'}}
    def dropdown(r, col, values):
        return {'setDataValidation': {'range': area(r, r+1, col, col+1), 'rule': {'condition': {'type': 'ONE_OF_LIST', 'values': [{'userEnteredValue': str(v)} for v in values]}, 'strict': True, 'showCustomUi': True}}}
    req = [
        {'setDataValidation': {'range': {'sheetId': sid}}},
        {'updateSheetProperties': {'properties': {'sheetId': sid, 'gridProperties': {'hideGridlines': True, 'frozenRowCount': 3, 'frozenColumnCount': 0}}, 'fields': 'gridProperties(hideGridlines,frozenRowCount,frozenColumnCount)'}},
        paint(0, height, {'backgroundColor': color('#FFFFFF'), 'textFormat': {'fontFamily': 'Arial', 'fontSize': 11, 'foregroundColor': color('#173B3D')}, 'verticalAlignment': 'MIDDLE', 'wrapStrategy': 'WRAP'}),
        {'repeatCell': {'range': area(3, height, 1, 4), 'cell': {'userEnteredFormat': {'numberFormat': {'type': 'TEXT'}}}, 'fields': 'userEnteredFormat.numberFormat'}},
        {'updateDimensionProperties': {'range': {'sheetId': sid, 'dimension': 'ROWS', 'startIndex': 0, 'endIndex': height}, 'properties': {'pixelSize': 36}, 'fields': 'pixelSize'}},
        {'updateDimensionProperties': {'range': {'sheetId': sid, 'dimension': 'COLUMNS', 'startIndex': 10, 'endIndex': width}, 'properties': {'hiddenByUser': True}, 'fields': 'hiddenByUser'}},
    ]
    for col, pixels in enumerate([255, 115, 115, 115, 70, 145, 135, 120, 65, 175]):
        req.append({'updateDimensionProperties': {'range': {'sheetId': sid, 'dimension': 'COLUMNS', 'startIndex': col, 'endIndex': col+1}, 'properties': {'pixelSize': pixels, 'hiddenByUser': False}, 'fields': 'pixelSize,hiddenByUser'}})
    req.append(paint(2, 3, {'backgroundColor': color('#0D9648'), 'textFormat': {'bold': True, 'foregroundColor': color('#FFFFFF')}, 'wrapStrategy': 'WRAP'}))
    req.append({'updateDimensionProperties': {'range': {'sheetId': sid, 'dimension': 'ROWS', 'startIndex': 2, 'endIndex': 3}, 'properties': {'pixelSize': 48}, 'fields': 'pixelSize'}})
    note = 'Reglamento 02/09/2026: máximo dos integrantes y un robot por equipo. Tres intentos por fase; se toma el menor tiempo válido de hasta 90 s. Tres fallos nuevos por fase; el juez registra sanciones por pérdida de línea o intervención. Reparación previa: 1 min; tolerancia de presentación: 1 min; espera de salida: 2 s. Esas esperas no se suman al recorrido. Avanzan 16 → 8 → 4; los tres mejores de la final definen el podio. El juez decide sanciones y desempates. Cierra la fase cuando se completen los intentos o la decisión del juez. No edites los resultados calculados ni las columnas ocultas.'
    req.append({'repeatCell': {'range': area(1, 2, 0, 1), 'cell': {'note': note}, 'fields': 'note'}})
    for r, row in enumerate(rows):
        if r in (0, 1) or row and str(row[0]).startswith('Competencia: '):
            req.append({'mergeCells': {'range': area(r, r+1), 'mergeType': 'MERGE_ALL'}})
            req.append(paint(r, r+1, {'backgroundColor': color('#F3F7F6'), 'textFormat': {'fontSize': 15 if r != 1 else 11, 'bold': r != 1, 'foregroundColor': color('#0D9648')}}))
        elif row and row[0] == 'Estado de fase':
            req.append(dropdown(r, 1, ['Abierta', 'Cerrada']))
        elif len(row) > 10 and row[10] and row[10] != 'id_equipo':
            req.extend([dropdown(r, 4, range(4)), dropdown(r, 5, ['Sin sanción', 'No presentó', 'Descalificado'])])
            req.append({'setDataValidation': {'range': area(r, r+1, 6, 7), 'rule': {'condition': {'type': 'NUMBER_BETWEEN', 'values': [{'userEnteredValue': '0'}, {'userEnteredValue': '4096'}]}, 'strict': True}}})
            req.append({'repeatCell': {'range': area(r, r+1, 7, 10), 'cell': {'userEnteredFormat': {'backgroundColor': color('#E6F4DE'), 'textFormat': {'bold': True, 'foregroundColor': color('#173B3D')}}}, 'fields': 'userEnteredFormat(backgroundColor,textFormat)'}})
    return req


def podium_format_requests(sid, rows, height, width, state):
    """Tres puestos por competencia, con selector nativo de equipos inscritos."""
    req = [
        {'updateSheetProperties': {'properties': {'sheetId': sid, 'gridProperties': {'hideGridlines': True, 'frozenRowCount': 1}}, 'fields': 'gridProperties(hideGridlines,frozenRowCount)'}},
        {'repeatCell': {'range': {'sheetId': sid, 'startRowIndex': 1, 'endRowIndex': height}, 'cell': {'userEnteredFormat': {'backgroundColor': color('#FFFFFF'), 'textFormat': {'fontFamily': 'Arial', 'fontSize': 11, 'foregroundColor': color('#173B3D')}, 'verticalAlignment': 'MIDDLE', 'wrapStrategy': 'WRAP'}}, 'fields': 'userEnteredFormat'}},
        {'updateDimensionProperties': {'range': {'sheetId': sid, 'dimension': 'ROWS', 'startIndex': 0, 'endIndex': height}, 'properties': {'pixelSize': 42}, 'fields': 'pixelSize'}},
        {'setDataValidation': {'range': {'sheetId': sid, 'startColumnIndex': 2, 'endColumnIndex': 3}}},
        {'updateDimensionProperties': {'range': {'sheetId': sid, 'dimension': 'COLUMNS', 'startIndex': 3, 'endIndex': width}, 'properties': {'hiddenByUser': True}, 'fields': 'hiddenByUser'}},
    ]
    for col, pixels in enumerate((240, 120, 360)):
        req.append({'updateDimensionProperties': {'range': {'sheetId': sid, 'dimension': 'COLUMNS', 'startIndex': col, 'endIndex': col+1}, 'properties': {'pixelSize': pixels, 'hiddenByUser': False}, 'fields': 'pixelSize,hiddenByUser'}})
    palette = {1: '#E6F4DE', 2: '#F3F7F6', 3: '#E0F3F0'}
    for index, row in enumerate(rows[1:], start=1):
        c = state.competitions.get(row[0]) if len(row) > 2 else None
        if not c or row[1] not in palette:
            continue
        req.append({'repeatCell': {'range': {'sheetId': sid, 'startRowIndex': index, 'endRowIndex': index+1, 'endColumnIndex': 3}, 'cell': {'userEnteredFormat': {'backgroundColor': color(palette[row[1]])}}, 'fields': 'userEnteredFormat.backgroundColor'}})
        req.append({'repeatCell': {'range': {'sheetId': sid, 'startRowIndex': index, 'endRowIndex': index+1, 'startColumnIndex': 1, 'endColumnIndex': 2}, 'cell': {'userEnteredFormat': {'numberFormat': {'type': 'NUMBER', 'pattern': '0".º puesto"'}}}, 'fields': 'userEnteredFormat.numberFormat'}})
        req.append({'setDataValidation': {'range': {'sheetId': sid, 'startRowIndex': index, 'endRowIndex': index+1, 'startColumnIndex': 2, 'endColumnIndex': 3}, 'rule': {'condition': {'type': 'ONE_OF_LIST', 'values': [{'userEnteredValue': v} for v in [UNDEFINED, *[t.nombre_equipo for t in c.teams]]]}, 'strict': True, 'showCustomUi': True}}})
    return req


def board_format_requests(sid,rows,height,width,rule_count=0):
    def area(r=0,end=None,c=0,last=None):
        out={'sheetId':sid,'startRowIndex':r,'startColumnIndex':c}
        if end is not None: out['endRowIndex']=end
        if last is not None: out['endColumnIndex']=last
        return out
    def fmt(r,end,c,last,style):
        return {'repeatCell':{'range':area(r,end,c,last),'cell':{'userEnteredFormat':style},'fields':'userEnteredFormat'}}
    req=[{'updateBorders':{'range':area(0,height,0,width),**{side:{'style':'NONE'} for side in ('top','bottom','left','right','innerHorizontal','innerVertical')}}},
         {'setDataValidation':{'range':{'sheetId':sid}}},
         {'updateSheetProperties':{'properties':{'sheetId':sid,'gridProperties':{'hideGridlines':True,'frozenRowCount':0}},'fields':'gridProperties(hideGridlines,frozenRowCount)'}},
         fmt(0,height,0,width,{'backgroundColor':color('#F3F7F6'),'textFormat':{'fontFamily':'Arial','fontSize':11,'foregroundColor':color('#173B3D')},'verticalAlignment':'MIDDLE','wrapStrategy':'WRAP'}),
         {'updateDimensionProperties':{'range':{'sheetId':sid,'dimension':'ROWS','startIndex':0,'endIndex':height},'properties':{'pixelSize':32},'fields':'pixelSize'}},
         fmt(0,1,0,2,{'backgroundColor':color('#F3F7F6'),'textFormat':{'fontSize':18,'bold':True,'foregroundColor':color('#0D9648')}})]
    # Cada tarjeta tiene nombre, estado e ID oculto; una columna deja el espacio.
    for col in range(width):
        role=col%STRIDE
        req.append({'updateDimensionProperties':{'range':{'sheetId':sid,'dimension':'COLUMNS','startIndex':col,'endIndex':col+1},'properties':{'hiddenByUser':role==2,'pixelSize':{0:270,1:150,2:80,3:24}[role]},'fields':'hiddenByUser,pixelSize'}})
    palette=['#0D9648','#00A99D','#0087C3','#45AD49','#0D9648','#0087C3']
    for start,name in sections(rows):
        req.append(fmt(start,start+2,0,2,{'backgroundColor':color('#F3F7F6'),'textFormat':{'bold':True,'fontSize':16,'foregroundColor':color('#173B3D')}}))
        control=start+2
        locked = 'Total y cupos cerrados' in str(value(rows,start+4,0))
        for col in ((5,) if locked else (1,5,9)):
            options = [2,4,8,16,32,64] if col==9 else list(range(1 if col==5 else 2,33 if col==5 else 101))
            current=value(rows,control,col)
            if isinstance(current,int) and current not in options: options.append(current)
            req.append({'setDataValidation':{'range':area(control,control+1,col,col+1),'rule':{'condition':{'type':'ONE_OF_LIST','values':[{'userEnteredValue':str(n)} for n in sorted(options)]},'strict':False,'showCustomUi':True}}})
            req.append(fmt(control,control+1,col,col+1,{'backgroundColor':color('#FFFFFF'),'textFormat':{'bold':True,'foregroundColor':color('#0087C3')},'horizontalAlignment':'CENTER'}))
        req.append(fmt(control,control+1,12,14,{'backgroundColor':color('#9FCF67'),'textFormat':{'bold':True,'foregroundColor':color('#173B3D')}}))
        for r in (start,start+1,start+3,start+4):
            req.append({'mergeCells':{'range':area(r,r+1,0,14 if r==start+4 else 6),'mergeType':'MERGE_ALL'}})
    for r,row in enumerate(rows):
        for col in range(0,min(width,CARDS_PER_ROW*STRIDE),STRIDE):
            if not str(value(rows,r,col+2)).startswith('group:'): continue
            end=r+1
            while end<len(rows) and value(rows,end,col+2) and not str(value(rows,end,col+2)).startswith('group:'): end+=1
            req.append(fmt(r+1,end,col,col+2,{'backgroundColor':color('#FFFFFF'),'textFormat':{'fontFamily':'Arial','fontSize':11,'foregroundColor':color('#173B3D')},'verticalAlignment':'MIDDLE','wrapStrategy':'WRAP'}))
            req.append(fmt(r,r+1,col,col+2,{'backgroundColor':color('#FFFFFF'),'textFormat':{'bold':True,'fontSize':12,'foregroundColor':color(palette[col//STRIDE])},'verticalAlignment':'MIDDLE'}))
            border={'style':'SOLID','color':color('#D4E6DF')}
            req.append({'updateBorders':{'range':area(r,end,col,col+2),'top':border,'bottom':border,'left':{'style':'SOLID_MEDIUM','color':color(palette[col//STRIDE])},'right':border}})
            req.append({'setDataValidation':{'range':area(r+1,end,col+1,col+2),'rule':{'condition':{'type':'ONE_OF_LIST','values':[{'userEnteredValue':s} for s in ('Pendiente','Clasifica','No clasifica')]},'strict':True,'showCustomUi':True}}})
    for _ in range(rule_count):
        req.append({'deleteConditionalFormatRule': {'sheetId':sid,'index':0}})
    for status,bg,fg in [('Pendiente','#EDF7F7','#0087C3'),('Clasifica','#E5F3D9','#0D9648'),('No clasifica','#EDF0EF','#607779')]:
        req.append({'addConditionalFormatRule':{'index':0,'rule':{
            'ranges':[{'sheetId':sid,'startColumnIndex':col,'endColumnIndex':col+1} for col in range(1,24,STRIDE)],
            'booleanRule':{'condition':{'type':'TEXT_EQ','values':[{'userEnteredValue':status}]},'format':{'backgroundColor':color(bg),'textFormat':{'foregroundColor':color(fg)}}}}}})
    return req
