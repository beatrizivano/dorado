import fs from 'node:fs/promises';
import path from 'node:path';
import {buildQuery,classify,normalize,parseGenbank,summarise} from './core.js';

const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const writeJson=(file,data)=>fs.writeFile(file,JSON.stringify(data,null,2),'utf8');

export async function runPipeline(config,root,update,cancelled,{fetchImpl=fetch,dataRoot=path.dirname(root)}={}){
  await fs.mkdir(root,{recursive:true});
  const warnings=[],source=new Map(),queries={};
  const warn=(stage,accession,cause)=>warnings.push({stage,accession,cause});
  const check=()=>{if(cancelled())throw new Error('ANALYSIS_CANCELLED');};
  const rate=config.api_key?10:3;
  // Serial pacing is deliberately conservative and shared across all requests in this run.
  let nextAllowed=0;
  async function request(endpoint,params){
    check();const now=Date.now();if(now<nextAllowed)await sleep(nextAllowed-now);
    nextAllowed=Date.now()+Math.ceil(1000/rate)+20;
    const form=new URLSearchParams({...params,db:'nucleotide',tool:'DoradoAcademic',email:config.email});
    if(config.api_key)form.set('api_key',config.api_key);
    const response=await fetchImpl(`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/${endpoint}`,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:form});
    if(!response.ok)throw new Error(`NCBI HTTP ${response.status}`);
    return endpoint==='esearch.fcgi'?response.json():response.text();
  }
  async function retry(fn,stage,label){for(let i=0;i<3;i++){check();try{return await fn();}catch(e){if(e.message==='ANALYSIS_CANCELLED')throw e;warn(stage,label,`tentativa ${i+1}: ${e.message}`);if(i<2)await sleep(1000*2**i);}}return null;}
  const species=config.species,genes=config.genes.length?config.genes:[''];
  const pairs=species.flatMap(s=>genes.map(g=>[s,g]));update('busca',1);
  for(const [index,[speciesName,gene]] of pairs.entries()){
    check();const q=buildQuery(speciesName,gene,config.template||'');queries[`${speciesName} | ${gene||'não filtrado'}`]=q;
    const first=await retry(()=>request('esearch.fcgi',{term:q,retmax:'0',retmode:'json',idtype:'acc'}),'busca',speciesName);
    if(!first?.esearchresult){warn('busca',speciesName,'Resposta de busca ausente ou inválida');continue;}
    const total=Number(first.esearchresult.count)||0;let count=0;
    // NCBI nucleotide eSearch has an effective 10k retrieval ceiling; report shortfall explicitly.
    const max=Math.min(total,10000);
    for(let start=0;start<max;start+=1000){
      const page=await retry(()=>request('esearch.fcgi',{term:q,retstart:String(start),retmax:String(Math.min(1000,max-start)),retmode:'json',idtype:'acc'}),'busca',speciesName);
      if(!page?.esearchresult?.idlist)break;
      for(const acc of page.esearchresult.idlist){
        const accession=String(acc);if(!source.has(accession))source.set(accession,{species:new Set(),genes:new Set()});
        source.get(accession).species.add(speciesName);source.get(accession).genes.add(gene||'não filtrado');count++;
      }
    }
    if(count!==total)warn('busca',speciesName,`Contagem NCBI ${total}; obtida ${count}. A recuperação acima de 10.000 requer particionamento adicional.`);
    update('busca',Math.round(100*(index+1)/pairs.length));
  }
  const sources=Object.fromEntries([...source].map(([acc,v])=>[acc,{species:[...v.species].sort(),genes:[...v.genes].sort()}]));
  await writeJson(path.join(root,'accessions.json'),sources);await writeJson(path.join(root,'queries.json'),queries);
  const cacheDir=path.join(dataRoot,'cache');await fs.mkdir(cacheDir,{recursive:true});
  const keys=[...source.keys()],meta={};update('download',0);
  for(let offset=0;offset<keys.length;offset+=100){
    check();const batch=keys.slice(offset,offset+100),remaining=[];
    for(const acc of batch){
      const filepath=path.join(cacheDir,acc.replace(/[^a-zA-Z0-9_.-]/g,'_')+'.json');
      try{const stat=await fs.stat(filepath);if(Date.now()-stat.mtimeMs<30*86400*1000){meta[acc]=JSON.parse(await fs.readFile(filepath,'utf8'));continue;}}catch{}
      remaining.push(acc);
    }
    if(remaining.length){
      const payload=await retry(()=>request('efetch.fcgi',{id:remaining.join(','),rettype:'gb',retmode:'text'}),'download',`lote ${offset/100+1}`);
      if(payload){const parsed=parseGenbank(payload,sources,warn);
        for(const [acc,rec] of Object.entries(parsed)){meta[acc]=rec;await writeJson(path.join(cacheDir,acc.replace(/[^a-zA-Z0-9_.-]/g,'_')+'.json'),rec);}
        for(const acc of remaining)if(!parsed[acc])warn('download',acc,'Registro não encontrado no lote recebido');
      }else warn('download',`lote ${offset/100+1}`,'Lote falho após 3 tentativas');
    }
    update('download',Math.round(100*Math.min(offset+100,keys.length)/Math.max(keys.length,1)));
  }
  update('extração',100);const records=[];
  for(const [index,[acc,rec]] of Object.entries(meta).entries()){
    check();const entry={...rec,species:sources[acc]?.species||[],genes:sources[acc]?.genes||[]};
    entry.classification=classify(entry,config.localities);
    if(entry.classification.invalid_coordinates)warn('classificação',acc,'Coordenadas inválidas');
    if(entry.organism&&!entry.species.some(s=>normalize(s)===normalize(entry.organism)))warn('classificação',acc,'Organismo diferente da espécie consultada');
    records.push(entry);if(index%100===0)update('classificação',Math.round(100*(index+1)/Math.max(Object.keys(meta).length,1)));
  }
  update('classificação',100);
  const summary=summarise(species,records,config.invalid,config.duplicates);
  await writeJson(path.join(root,'records.json'),records);await writeJson(path.join(root,'summary.json'),summary);await writeJson(path.join(root,'warnings.json'),warnings);
  update('resumo',100);return {summary,records,warnings,queries};
}
