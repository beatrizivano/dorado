import express from 'express';
import multer from 'multer';
import ExcelJS from 'exceljs';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomUUID} from 'node:crypto';
import {parseNames,terms,buildQuery} from './core.js';
import {runPipeline} from './pipeline.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const dataRoot=path.resolve(process.env.DORADO_DATA||path.join(root,'data'));
const jobsRoot=path.join(dataRoot,'jobs');await fs.mkdir(jobsRoot,{recursive:true});
const app=express();app.disable('x-powered-by');app.use(express.json({limit:'1mb'}));
app.use('/static',express.static(path.join(root,'dorado/static')));
app.get('/',(_,res)=>res.sendFile(path.join(root,'dorado/static/index.html')));
const active=new Set();
const asyncRoute=fn=>(req,res,next)=>Promise.resolve(fn(req,res,next)).catch(next);
const json=(file,data)=>fs.writeFile(file,JSON.stringify(data,null,2),'utf8');
function error(status,detail){const e=new Error(detail);e.status=status;throw e;}
function validate(body){
  const names=parseNames(body.names||'');if(!names.valid.length)error(422,'Informe ao menos uma espécie válida');
  const genes=terms(body.genes||[]);const template=String(body.template||'');
  try{buildQuery(names.valid[0],genes[0]||'',template);}catch(e){error(422,e.message);}
  return {names,genes,template};
}
function jobDir(id){if(!/^[0-9a-f]{32}$/.test(id))error(404,'Análise inexistente');return path.join(jobsRoot,id);}
async function state(id){try{return JSON.parse(await fs.readFile(path.join(jobDir(id),'state.json'),'utf8'));}catch(e){if(e.status)throw e;error(404,'Análise inexistente');}}
async function saveState(id,value){const dir=jobDir(id);const temp=path.join(dir,'state.tmp');await json(temp,value);await fs.rename(temp,path.join(dir,'state.json'));}
async function readJson(file){return JSON.parse(await fs.readFile(file,'utf8'));}
async function result(id){await state(id);const dir=jobDir(id);try{return {summary:await readJson(path.join(dir,'summary.json')),records:await readJson(path.join(dir,'records.json')),warnings:await readJson(path.join(dir,'warnings.json')),config:await readJson(path.join(dir,'config.json'))};}catch{error(409,'Análise ainda não concluída');}}
async function execute(id,config){
  const dir=jobDir(id);
  let current=await state(id);
  // Queue writes to prevent out-of-order updates at stage boundaries.
  let updates=Promise.resolve();
  const update=(stage,progress)=>{updates=updates.then(async()=>{current={...current,stage,progress};await saveState(id,current);});};
  try{
    const {warnings}=await runPipeline(config,dir,update,()=>cancelled.has(id),{dataRoot});
    await updates;current={...current,status:warnings.length?'concluída com avisos':'concluída',stage:'concluída',progress:100,warnings_count:warnings.length};await saveState(id,current);
  }catch(e){await updates;current={...current,status:e.message==='ANALYSIS_CANCELLED'?'cancelada':'erro',stage:e.message==='ANALYSIS_CANCELLED'?'interrompida':current.stage,...(e.message==='ANALYSIS_CANCELLED'?{}:{error:e.message})};await saveState(id,current);}finally{active.delete(id);cancelled.delete(id);}
}
const cancelled=new Set();
app.post('/api/names',(req,res)=>res.json(parseNames(req.body?.names||'')));
app.post('/api/preview',(req,res)=>{try{const {names,genes,template}=validate(req.body||{});const sample=buildQuery(names.valid[0],genes[0]||'',template);const queries=names.valid.length*Math.max(1,genes.length);res.json({names,queries,sample_query:sample,minimum_seconds:Math.round(10*queries/(req.body.api_key?10:3))/10});}catch(e){res.status(e.status||422).json({detail:e.message});}});
app.post('/api/jobs',asyncRoute(async(req,res)=>{
  const body=req.body||{}, {names,genes,template}=validate(body);
  if(typeof body.email!=='string'||!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(body.email)||body.email.length>254)error(422,'Informe um e-mail válido para identificação NCBI');
  const id=randomUUID().replaceAll('-','');const dir=jobDir(id);await fs.mkdir(dir,{recursive:true});
  const config={species:names.valid,invalid:names.invalid,duplicates:names.duplicates,genes,localities:Object.fromEntries(['countries','states','cities','keywords'].map(k=>[k,terms(body.localities?.[k]||[])])),template,email:body.email,api_key:typeof body.api_key==='string'?body.api_key:''};
  await json(path.join(dir,'config.json'),{...config,api_key:''});
  const initial={id,status:'executando',stage:'iniciando',progress:0,created_at:new Date().toISOString(),species:names.valid.length,warnings_count:0};await saveState(id,initial);
  active.add(id);setImmediate(()=>execute(id,config));res.json(initial);
}));
app.get('/api/jobs',asyncRoute(async(req,res)=>{const ids=await fs.readdir(jobsRoot,{withFileTypes:true});const jobs=await Promise.all(ids.filter(x=>x.isDirectory()).map(async x=>{try{return await state(x.name);}catch{return null;}}));res.json(jobs.filter(Boolean).sort((a,b)=>b.created_at.localeCompare(a.created_at)));}));
app.get('/api/jobs/:id',asyncRoute(async(req,res)=>res.json(await state(req.params.id))));
app.get('/api/jobs/:id/result',asyncRoute(async(req,res)=>res.json(await result(req.params.id))));
app.post('/api/jobs/:id/cancel',asyncRoute(async(req,res)=>{const s=await state(req.params.id);if(s.status==='executando')cancelled.add(s.id);res.json({message:'Cancelamento solicitado; aplicado entre operações.'});}));
app.post('/api/jobs/:id/duplicate',asyncRoute(async(req,res)=>{await state(req.params.id);res.json(await readJson(path.join(jobDir(req.params.id),'config.json')));}));
app.delete('/api/jobs/:id',asyncRoute(async(req,res)=>{const s=await state(req.params.id);if(active.has(s.id))error(409,'Cancele e aguarde a interrupção antes de excluir');await fs.rm(jobDir(s.id),{recursive:true,force:true});res.json({ok:true});}));

const upload=multer({storage:multer.memoryStorage(),limits:{fileSize:5*1024*1024}});
app.post('/api/upload',upload.single('file'),asyncRoute(async(req,res)=>{
  if(!req.file)error(422,'Arquivo ausente');const name=req.file.originalname.toLowerCase();
  if(name.endsWith('.csv')){
    let text;try{text=new TextDecoder('utf-8',{fatal:true}).decode(req.file.buffer).replace(/^\uFEFF/,'');}catch{error(422,'CSV inválido ou codificação não UTF-8');}
    const delimiter=(text.split(/\r?\n/,1)[0].match(/;/g)||[]).length>(text.split(/\r?\n/,1)[0].match(/,/g)||[]).length?';':',';
    const rows=parseCsv(text,delimiter);res.json({sheets:['CSV'],columns:rows[0]||[],preview:rows.slice(0,10),rows});return;
  }
  if(name.endsWith('.xlsx')){
    const workbook=new ExcelJS.Workbook();try{await workbook.xlsx.load(req.file.buffer);}catch{error(422,'Planilha inválida');}
    const datasets={};for(const sheet of workbook.worksheets)datasets[sheet.name]=sheet.getSheetValues().slice(1).map(r=>Array.from({length:sheet.columnCount},(_,i)=>String(r?.[i+1]??'')));
    res.json({sheets:Object.keys(datasets),datasets,preview:Object.values(datasets)[0]?.slice(0,10)||[]});return;
  }
  error(415,'Somente arquivos CSV e XLSX são permitidos');
}));
function parseCsv(text,delimiter){let rows=[],row=[],cell='',quoted=false;for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}else if(c===delimiter&&!quoted){row.push(cell);cell='';}else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(v=>v!==''))rows.push(row);row=[];cell='';}else cell+=c;}row.push(cell);if(row.some(v=>v!==''))rows.push(row);if(quoted)error(422,'CSV inválido');return rows;}
const safeCell=value=>{const raw=typeof value==='object'&&value!==null?JSON.stringify(value):value;return typeof raw==='string'&&/^[=+\-@]/.test(raw)?"'"+raw:raw??'';};
function tabular(data){return data.records.map(r=>{const c=r.classification;return {accession:r.accession,organism:r.organism,species:r.species.join('; '),genes:r.genes.join('; '),geo_loc_name:c.raw_locality.join('; '),lat_lon:(r.metadata.lat_lon||[]).join('; '),has_locality:c.has_locality,relevance:c.relevance,origin:c.locality_origin,inferred:c.inferred||''};});}
function makeCsv(rows,columns){const escape=v=>{const str=String(safeCell(v));return /[",\r\n;]/.test(str)?'"'+str.replaceAll('"','""')+'"':str;};return '\uFEFF'+[columns.join(','),...rows.map(row=>columns.map(k=>escape(row[k])).join(','))].join('\r\n');}
app.get('/api/jobs/:id/export/:format',asyncRoute(async(req,res)=>{
  const data=await result(req.params.id),rows=tabular(data),columns=['accession','organism','species','genes','geo_loc_name','lat_lon','has_locality','relevance','origin','inferred'];
  const format=req.params.format;res.set('Content-Disposition',`attachment; filename="dorado-${req.params.id}.${format}"`);
  if(format==='json'){res.type('json').send(JSON.stringify(data,null,2));return;}
  if(format==='csv'){res.type('text/csv; charset=utf-8').send(makeCsv(rows,columns));return;}
  if(format==='xlsx'){
    const wb=new ExcelJS.Workbook();const {summary,config}=data;
    const sheets={Resumo:Object.entries(summary).filter(([k])=>!['species','localities','matrix'].includes(k)).map(([indicador,valor])=>({indicador,valor})), 'Espécie Gene Relevância':summary.matrix,Localidades:summary.localities,Registros:rows,Parâmetros:Object.entries(config).map(([campo,valor])=>({campo,valor}))};
    for(const [name,items] of Object.entries(sheets)){const ws=wb.addWorksheet(name);const fields=items[0]?Object.keys(items[0]):['informação'];ws.columns=fields.map(key=>({header:key,key}));for(const item of items)ws.addRow(Object.fromEntries(fields.map(key=>[key,safeCell(item[key])])));ws.views=[{state:'frozen',ySplit:1}];if(items.length)ws.autoFilter={from:'A1',to:{row:items.length+1,column:fields.length}};}
    res.type('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');res.send(Buffer.from(await wb.xlsx.writeBuffer()));return;
  }
  error(404,'Formato não suportado');
}));
app.use((err,req,res,next)=>{if(res.headersSent)return next(err);res.status(err.code==='LIMIT_FILE_SIZE'?413:err.status||500).json({detail:err.code==='LIMIT_FILE_SIZE'?'Arquivo maior que 5 MB':err.message||'Erro interno'});});
const port=Number(process.env.PORT||8000);
if(process.env.NODE_ENV!=='test')app.listen(port,()=>console.log(`Dorado: http://localhost:${port}`));
export {app};
