"""Dorado: computational core evolved from the six-script Python legacy pipeline.
No taxonomy reconciliation or nucleotide-sequence persistence.
"""
from __future__ import annotations
import csv, io, json, re, time, unicodedata
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from Bio import Entrez, SeqIO

GENE_SYNONYMS = {
    '12S': ['12S', '12S ribosomal RNA'],
    '16S': ['16S', '16S ribosomal RNA'],
    'COI': ['COI', 'COX1', 'CO1', 'cytochrome c oxidase subunit I', 'cytochrome oxidase subunit 1'],
}
ABSENCE = {'', 'unknown', 'n/a', 'na', 'missing', 'not collected', 'not applicable', 'not provided', 'restricted access', 'none', 'null'}
FIELDS = ['collection_date','isolate','db_xref','geo_loc_name','country','lat_lon','specimen_voucher','isolation_source','note']
LEVELS = ['palavra-chave','cidade','estado','país','outra localidade','sem localidade','não avaliada']
COUNTRIES = {'br':'brazil','bra':'brazil','brasil':'brazil','brazil':'brazil','argentina':'argentina','ar':'argentina'}
STATES = {'pr':'parana','parana':'parana','paraná':'parana','parana state':'parana'}

def normalize(text):
    s = unicodedata.normalize('NFKD', str(text or ''))
    return re.sub(r'\s+', ' ', ''.join(c for c in s if not unicodedata.combining(c)).casefold()).strip()

def parse_names(raw):
    tokens = re.split(r'[,;\n\r]+', raw or '')
    valid, duplicate, invalid, seen = [], [], [], set()
    for token in tokens:
        token = ' '.join(token.split())
        if not token: continue
        parts = token.split()
        if len(parts) != 2 or not all(re.fullmatch(r'[A-Za-zÀ-ÿ-]+', p) for p in parts):
            invalid.append(token); continue
        name = parts[0].capitalize() + ' ' + parts[1].lower()
        if normalize(name) in seen: duplicate.append(token)
        else: valid.append(name);seen.add(normalize(name))
    return {'valid':valid,'duplicates':duplicate,'invalid':invalid}

def terms(raw):
    if isinstance(raw,list): return list(dict.fromkeys(v.strip() for v in raw if isinstance(v,str) and v.strip()))
    return list(dict.fromkeys(x.strip() for x in re.split(r'[,;\n]+', raw or '') if x.strip()))

def gene_query(gene):
    if not gene: return ''
    variants=GENE_SYNONYMS.get(gene.upper())
    if not variants:return f' AND ({gene}[All Fields])'
    return ' AND ('+' OR '.join(f'"{s}"[All Fields]' for s in variants)+')'

def build_query(species, gene='', template=''):
    base=f'"{species}"[Organism]'
    if template:
        if '{especie}' not in template: raise ValueError('A consulta avançada precisa conter {especie}.')
        return template.replace('{especie}',base).replace('{gene}',gene_query(gene).removeprefix(' AND '))
    return base + gene_query(gene)

def parse_coords(s):
    if not s: return None
    match=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*([NS])\s*[,; ]+\s*(\d+(?:\.\d+)?)\s*([EW])\s*',s,re.I)
    if not match:return None
    lat=float(match[1])*(-1 if match[2].upper()=='S' else 1)
    lon=float(match[3])*(-1 if match[4].upper()=='W' else 1)
    return (lat,lon) if abs(lat)<=90 and abs(lon)<=180 else None

def meaningful(values):
    return [str(v).strip() for v in (values if isinstance(values,list) else [values]) if normalize(v) not in ABSENCE]

def whole_match(value, option):
    a,b=normalize(value),normalize(option)
    return bool(b and re.search(r'(?<!\w)'+re.escape(b)+r'(?!\w)',a))

def classify(record, loc):
    meta=record.get('metadata',{})
    geo=meaningful(meta.get('geo_loc_name',[]))+meaningful(meta.get('country',[]))
    raw_coords=meaningful(meta.get('lat_lon',[]))
    coords=next((p for p in (parse_coords(x) for x in raw_coords) if p),None)
    text=' '.join(geo)
    has=bool(geo or coords)
    places={k:terms(loc.get(k,[])) for k in ('countries','states','cities','keywords')}
    opts=any(places.values())
    country=text.split(':',1)[0] if geo else ''
    desc=' '.join(g.split(':',1)[-1] for g in geo)
    matches={
        'country': any(COUNTRIES.get(normalize(x),normalize(x))==COUNTRIES.get(normalize(country),normalize(country)) for x in places['countries']) if country else False,
        'state':any(whole_match(desc,STATES.get(normalize(x),x)) for x in places['states']),
        'city':any(whole_match(desc,x) for x in places['cities']),
        'keyword':any(whole_match(desc,x) for x in places['keywords']),
    }
    level = ('sem localidade' if not has else 'não avaliada' if not opts else
             'palavra-chave' if matches['keyword'] else 'cidade' if matches['city'] else
             'estado' if matches['state'] else 'país' if matches['country'] else 'outra localidade')
    return {'has_locality':has,'locality_origin':'ambos' if geo and coords else 'texto' if geo else 'coordenadas' if coords else 'ausente',
            'relevance':level,'matches':matches,'coordinates':list(coords) if coords else None,
            'invalid_coordinates':bool(raw_coords and not coords),'raw_locality':geo,'country_text':country,'description':desc,
            'inferred':None}

def extract_genbank(text, source, warn):
    result={}
    for entry in SeqIO.parse(io.StringIO(text),'genbank'):
        try:
            acc=entry.id
            metadata=defaultdict(list)
            for ft in entry.features:
                for key, vals in ft.qualifiers.items():
                    if key in FIELDS:
                        for v in vals:
                            if str(v) not in metadata[key]:metadata[key].append(str(v))
            result[acc]={'accession':acc,'organism':str(entry.annotations.get('organism') or ''),
                         'metadata':dict(metadata),'species':sorted(source.get(acc,{}).get('species',[])),
                         'genes':sorted(source.get(acc,{}).get('genes',[]))}
            if not result[acc]['organism']:warn('extração',acc,'Organismo ausente')
        except Exception as exc: warn('extração',str(getattr(entry,'id','?')),str(exc))
    return result

def summarise(species,records, loc, invalid=None,duplicates=None):
    per_species={s:{'species':s,'total':0,'with_locality':0,'without_locality':0,'with_coordinates':0} for s in species}
    counts=Counter();found=set();locality=defaultdict(lambda:{'records':0,'species':set(),'origin':set()});matrix=Counter()
    for rec in records:
        classification=rec['classification']; counts[classification['relevance']]+=1
        for s in rec['species']:
            if s not in per_species:continue
            found.add(s);row=per_species[s];row['total']+=1;row['with_locality']+=int(classification['has_locality']);row['without_locality']+=int(not classification['has_locality']);row['with_coordinates']+=int(classification['coordinates'] is not None)
            for gene in rec['genes'] or ['não filtrado']: matrix[(s,gene,classification['relevance'])]+=1
        for place in classification['raw_locality']:
            item=locality[place];item['records']+=1;item['species'].update(rec['species']);item['origin'].add('texto')
    count=len(records); with_loc=sum(int(r['classification']['has_locality']) for r in records)
    return {'submitted':len(species)+len(invalid or [])+len(duplicates or []),'valid':len(species),'duplicates':duplicates or [],'invalid':invalid or [],
       'with_records':len(found),'without_records':sorted(set(species)-found),'species_coverage_pct':round(100*len(found)/len(species),2) if species else 0,
       'total_records':count,'with_locality':with_loc,'without_locality':count-with_loc,
       'with_coordinates':sum(int(r['classification']['coordinates'] is not None) for r in records),
       'relevance':dict(counts),'species':list(per_species.values()),
       'localities':[{'name':k,'records':v['records'],'species':len(v['species']),'origin':sorted(v['origin'])} for k,v in sorted(locality.items())],
       'matrix':[{'species':s,'gene':g,'relevance':lev,'records':n} for (s,g,lev),n in sorted(matrix.items())]}

def run_pipeline(config, root, update:Callable, cancelled:Callable):
    """Runs sequential phases; checkpoints after successful download batches."""
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    species=config['species'];genes=config.get('genes') or ['']; queries={};source=defaultdict(lambda:{'species':set(),'genes':set()});warnings=[]
    def warn(stage, accession, cause):warnings.append({'stage':stage,'accession':accession,'cause':cause})
    Entrez.email=config['email']; Entrez.tool='DoradoAcademic';Entrez.api_key=config.get('api_key') or None
    def check():
        if cancelled(): raise InterruptedError('Análise cancelada')
    rate=10 if config.get('api_key') else 3;last_request=[0.0]
    def throttle():
        delta=time.monotonic()-last_request[0]
        if delta<1/rate:time.sleep(1/rate-delta)
        last_request[0]=time.monotonic()
    def retry(operation,stage,label):
        for attempt in range(3):
            check()
            try:throttle();return operation()
            except Exception as e:
                warn(stage,label,f'tentativa {attempt+1}: {e}')
                if attempt<2:time.sleep(min(2**attempt,4))
        return None
    pairs=[(s,g) for s in species for g in genes]
    update('busca',1)
    for index,(s,g) in enumerate(pairs):
        check();q=build_query(s,g,config.get('template',''));queries[f'{s} | {g or "não filtrado"}']=q
        def initial():
            with Entrez.esearch(db='nucleotide',term=q,retmax=0) as h:return Entrez.read(h)
        response=retry(initial,'busca',s)
        if response is None:continue
        total=int(response.get('Count',0));collected=0
        for start in range(0,total,10000):
            def page():
                with Entrez.esearch(db='nucleotide',term=q,retstart=start,retmax=min(10000,total-start),idtype='acc') as h:return Entrez.read(h)
            data=retry(page,'busca',s)
            if data is None:break
            ids=data.get('IdList',[]);collected+=len(ids)
            for accession in ids:source[str(accession)]['species'].add(s);source[str(accession)]['genes'].add(g or 'não filtrado')
        if collected!=total:warn('busca',s,f'Contagem NCBI {total}; obtida {collected}. A API pode impor limites de paginação.')
        update('busca',round(100*(index+1)/max(len(pairs),1)))
    (root/'accessions.json').write_text(json.dumps({k:{x:sorted(v[x]) for x in ('species','genes')} for k,v in source.items()},ensure_ascii=False,indent=2))
    (root/'queries.json').write_text(json.dumps(queries,ensure_ascii=False,indent=2))
    keys=list(source);meta={};cache=root.parent.parent/'cache';cache.mkdir(parents=True,exist_ok=True)
    update('download',0)
    for idx in range(0,len(keys),100):
        check();part=keys[idx:idx+100];remaining=[]
        for acc in part:
            p=cache/(re.sub(r'[^a-zA-Z0-9_.-]','_',acc)+'.json')
            if p.exists() and time.time()-p.stat().st_mtime<30*86400:
                try:meta[acc]=json.loads(p.read_text());continue
                except Exception:pass
            remaining.append(acc)
        if remaining:
            def download():
                with Entrez.efetch(db='nucleotide',id=','.join(remaining),rettype='gb',retmode='text') as h:return h.read()
            payload=retry(download,'download',f'lote {idx//100+1}')
            if payload:
                extracted=extract_genbank(payload,source,warn)
                for acc,rec in extracted.items():
                    meta[acc]=rec
                    (cache/(re.sub(r'[^a-zA-Z0-9_.-]','_',acc)+'.json')).write_text(json.dumps(rec,ensure_ascii=False))
            else:warn('download',f'lote {idx//100+1}','Lote falho após 3 tentativas')
        update('download',round(100*min(idx+100,len(keys))/max(len(keys),1)))
    update('extração',100)
    records=[]
    for index,(acc,rec) in enumerate(meta.items()):
        check();r=dict(rec);r['species']=sorted(source.get(acc,{}).get('species',[]));r['genes']=sorted(source.get(acc,{}).get('genes',[]))
        classification=classify(r,config.get('localities',{}));r['classification']=classification
        if classification['invalid_coordinates']:warn('classificação',acc,'Coordenadas inválidas')
        if r['organism'] and all(normalize(r['organism'])!=normalize(s) for s in r['species']):warn('classificação',acc,'Organismo diferente da espécie consultada')
        records.append(r)
        if index%100==0:update('classificação',round(100*(index+1)/max(len(meta),1)))
    update('classificação',100);summary=summarise(species,records,config.get('localities',{}),config.get('invalid'),config.get('duplicates'))
    (root/'records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));(root/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    (root/'warnings.json').write_text(json.dumps(warnings,ensure_ascii=False,indent=2))
    update('resumo',100)
    return summary,records,warnings,queries
