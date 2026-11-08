from __future__ import annotations
import csv, io, json, os, threading, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from openpyxl import Workbook, load_workbook
from .core import parse_names, terms, build_query, run_pipeline, LEVELS

BASE=Path(os.environ.get('DORADO_DATA',Path(__file__).resolve().parent.parent/'data'))
BASE.mkdir(parents=True,exist_ok=True)
JOBS=BASE/'jobs'; JOBS.mkdir(exist_ok=True)
app=FastAPI(title='Dorado API',version='0.2.0')
app.mount('/static',StaticFiles(directory=Path(__file__).parent/'static'),name='static')
active={};mutex=threading.Lock()

class Request(BaseModel):
    names:str
    genes:list[str]=Field(default_factory=list)
    localities:dict=Field(default_factory=dict)
    template:str=''
    email:str
    api_key:str=''

def job_path(jobid):
    if not all(c in '0123456789abcdef' for c in jobid) or len(jobid)!=32:raise HTTPException(404,'Análise inexistente')
    path=JOBS/jobid
    if not path.exists():raise HTTPException(404,'Análise inexistente')
    return path

def state(id):return json.loads((job_path(id)/'state.json').read_text())

def save_state(id,data):
    path=job_path(id);temp=path/'state.tmp';temp.write_text(json.dumps(data,ensure_ascii=False));temp.replace(path/'state.json')

@app.get('/')
def home():return FileResponse(Path(__file__).parent/'static'/'index.html')

@app.post('/api/names')
def validate_names(body:dict):return parse_names(body.get('names',''))

@app.post('/api/preview')
def preview(body:Request):
    names=parse_names(body.names)
    if not names['valid']:raise HTTPException(422,'Informe ao menos uma espécie válida')
    genes=body.genes or ['']
    try:sample=build_query(names['valid'][0],genes[0],body.template)
    except ValueError as e:raise HTTPException(422,str(e))
    return {'names':names,'queries':len(names['valid'])*len(genes),'sample_query':sample,'minimum_seconds':round(len(names['valid'])*len(genes)/(10 if body.api_key else 3),1)}

def execute(id,config):
    def update(stage,pct):
        with mutex:
            item=state(id);item['stage']=stage;item['progress']=pct;save_state(id,item)
    def cancelled():return (job_path(id)/'cancel').exists()
    try:
        summary,records,warnings,queries=run_pipeline(config,job_path(id),update,cancelled)
        with mutex:
            item=state(id);item.update(status='concluída com avisos' if warnings else 'concluída',stage='concluída',progress=100,warnings_count=len(warnings));save_state(id,item)
    except InterruptedError:
        with mutex:
            item=state(id);item.update(status='cancelada',stage='interrompida');save_state(id,item)
    except Exception as e:
        with mutex:
            item=state(id);item.update(status='erro',error=str(e));save_state(id,item)
    finally:active.pop(id,None)

@app.post('/api/jobs')
def start(body:Request):
    names=parse_names(body.names)
    if not names['valid']:raise HTTPException(422,'Informe ao menos uma espécie válida')
    if '@' not in body.email or len(body.email)>254:raise HTTPException(422,'Informe um e-mail válido para identificação NCBI')
    try:build_query(names['valid'][0],(body.genes or [''])[0],body.template)
    except ValueError as e:raise HTTPException(422,str(e))
    id=uuid.uuid4().hex;path=JOBS/id;path.mkdir()
    config={'species':names['valid'],'invalid':names['invalid'],'duplicates':names['duplicates'],
        'genes':list(dict.fromkeys(g.strip() for g in body.genes if g.strip())),
        'localities':{k:terms(body.localities.get(k,[])) for k in ('countries','states','cities','keywords')},
        'template':body.template,'email':body.email,'api_key':body.api_key}
    (path/'config.json').write_text(json.dumps({**config,'api_key':''},ensure_ascii=False,indent=2))
    save_state(id,{'id':id,'status':'executando','stage':'iniciando','progress':0,'created_at':datetime.now(timezone.utc).isoformat(),'species':len(names['valid']),'warnings_count':0})
    thread=threading.Thread(target=execute,args=(id,config),daemon=True);active[id]=thread;thread.start()
    return state(id)

@app.get('/api/jobs')
def history():
    return sorted([json.loads(p.read_text()) for p in JOBS.glob('*/state.json')],key=lambda r:r['created_at'],reverse=True)

@app.get('/api/jobs/{id}')
def get_job(id:str):return state(id)

@app.get('/api/jobs/{id}/result')
def result(id:str):
    path=job_path(id)
    if not (path/'summary.json').exists():raise HTTPException(409,'Análise ainda não concluída')
    return {'summary':json.loads((path/'summary.json').read_text()),'records':json.loads((path/'records.json').read_text()),'warnings':json.loads((path/'warnings.json').read_text()),'config':json.loads((path/'config.json').read_text())}

@app.post('/api/jobs/{id}/cancel')
def cancel(id:str):
    (job_path(id)/'cancel').touch()
    return {'message':'Cancelamento solicitado; aplicado entre operações.'}

@app.post('/api/jobs/{id}/duplicate')
def duplicate(id:str):return json.loads((job_path(id)/'config.json').read_text())

@app.delete('/api/jobs/{id}')
def delete(id:str):
    if id in active:raise HTTPException(409,'Cancele e aguarde a interrupção antes de excluir')
    import shutil
    shutil.rmtree(job_path(id));return {'ok':True}

@app.post('/api/upload')
async def upload(file:UploadFile=File(...)):
    content=await file.read(5*1024*1024+1)
    if len(content)>5*1024*1024:raise HTTPException(413,'Arquivo maior que 5 MB')
    name=(file.filename or '').lower()
    if name.endswith('.csv'):
        try:
            text=content.decode('utf-8-sig');dialect=csv.Sniffer().sniff(text[:2048],delimiters=',;')
            rows=list(csv.reader(io.StringIO(text),dialect))
        except (UnicodeError,csv.Error) as e:raise HTTPException(422,'CSV inválido ou codificação não UTF-8') from e
        return {'sheets':['CSV'],'columns':rows[0] if rows else [],'preview':rows[:10],'rows':rows}
    if name.endswith('.xlsx'):
        try:
            book=load_workbook(io.BytesIO(content),read_only=True,data_only=True)
            sheets={sheet.title:[[str(v) if v is not None else '' for v in row] for row in sheet.iter_rows(values_only=True)] for sheet in book.worksheets}
            book.close()
        except Exception as e:raise HTTPException(422,'Planilha inválida') from e
        return {'sheets':list(sheets),'datasets':sheets,'preview':next(iter(sheets.values()),[])[:10]}
    raise HTTPException(415,'Somente arquivos CSV e XLSX são permitidos')

def safe_cell(s):
    if isinstance(s,(dict,list)):s=json.dumps(s,ensure_ascii=False)
    if isinstance(s,str) and s.startswith(('=','+','-','@')):return "'"+s
    return s

def tabular(result):
    rows=[]
    for r in result['records']:
        c=r['classification'];rows.append({'accession':r['accession'],'organism':r['organism'],
            'species':'; '.join(r['species']),'genes':'; '.join(r['genes']),
            'geo_loc_name':'; '.join(c['raw_locality']),'lat_lon':'; '.join(r['metadata'].get('lat_lon',[])),
            'has_locality':c['has_locality'],'relevance':c['relevance'],'origin':c['locality_origin'],
            'inferred':c['inferred'] or ''})
    return rows

@app.get('/api/jobs/{id}/export/{format}')
def export(id:str,format:str):
    data=result(id);rows=tabular(data);headers=list(rows[0]) if rows else ['accession','organism','species','genes','geo_loc_name','lat_lon','has_locality','relevance','origin','inferred']
    if format=='json':return Response(content=json.dumps(data,ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="dorado-{id}.json"'})
    if format=='csv':
        out=io.StringIO();writer=csv.DictWriter(out,fieldnames=headers);writer.writeheader();writer.writerows([{k:safe_cell(v) for k,v in r.items()} for r in rows])
        return Response(content='\ufeff'+out.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="dorado-{id}.csv"'})
    if format=='xlsx':
        wb=Workbook();wb.remove(wb.active)
        sheets={'Resumo':[{'indicador':k,'valor':v if not isinstance(v,(list,dict)) else json.dumps(v,ensure_ascii=False)} for k,v in data['summary'].items() if k not in ('species','localities','matrix')],
            'Espécie Gene Relevância':data['summary']['matrix'],'Localidades':data['summary']['localities'],
            'Registros':rows,'Parâmetros': [{'campo':k,'valor':json.dumps(v,ensure_ascii=False)} for k,v in data['config'].items()]}
        for name,items in sheets.items():
            ws=wb.create_sheet(name);cols=list(items[0]) if items else ['informação'];ws.append(cols)
            for item in items:ws.append([safe_cell(item.get(k,'')) for k in cols])
            ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
        bio=io.BytesIO();wb.save(bio)
        return Response(content=bio.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="dorado-{id}.xlsx"'})
    raise HTTPException(404,'Formato não suportado')
