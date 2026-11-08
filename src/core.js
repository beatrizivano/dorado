const GENE_SYNONYMS = {
  '12S':['12S','12S ribosomal RNA'],
  '16S':['16S','16S ribosomal RNA'],
  'COI':['COI','COX1','CO1','cytochrome c oxidase subunit I','cytochrome oxidase subunit 1']
};
const ABSENCE = new Set(['','unknown','n/a','na','missing','not collected','not applicable','not provided','restricted access','none','null']);
const FIELDS = new Set(['collection_date','isolate','db_xref','geo_loc_name','country','lat_lon','specimen_voucher','isolation_source','note']);
const COUNTRIES = {'br':'brazil','bra':'brazil','brasil':'brazil','brazil':'brazil','argentina':'argentina','ar':'argentina'};
const STATES = {'pr':'parana','parana':'parana','parana state':'parana'};

export function normalize(v='') { return String(v??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim(); }
export function parseNames(raw='') {
  const valid=[],duplicates=[],invalid=[],seen=new Set();
  for(const candidate of String(raw).split(/[,;\r\n]+/)){
    const token=candidate.trim().replace(/\s+/g,' ');if(!token)continue;
    const parts=token.split(' ');
    if(parts.length!==2||!parts.every(x=>/^[\p{L}-]+$/u.test(x))){invalid.push(token);continue;}
    const name=parts[0].charAt(0).toUpperCase()+parts[0].slice(1).toLowerCase()+' '+parts[1].toLowerCase();
    if(seen.has(normalize(name)))duplicates.push(token);else{seen.add(normalize(name));valid.push(name);}
  }
  return {valid,duplicates,invalid};
}
export function terms(values){const arr=Array.isArray(values)?values:String(values||'').split(/[,;\n]+/);return [...new Set(arr.filter(x=>typeof x==='string').map(x=>x.trim()).filter(Boolean))];}
export function geneQuery(gene=''){
  if(!gene)return '';
  const aliases=GENE_SYNONYMS[gene.toUpperCase()];
  return aliases?' AND ('+aliases.map(g=>`"${g}"[All Fields]`).join(' OR ')+')':` AND (${gene}[All Fields])`;
}
export function buildQuery(species,gene='',template=''){
  const base=`"${species}"[Organism]`;
  if(template){if(!template.includes('{especie}'))throw new Error('A consulta avançada precisa conter {especie}.');return template.replaceAll('{especie}',base).replaceAll('{gene}',geneQuery(gene).replace(/^ AND /,''));}
  return base+geneQuery(gene);
}
export function parseCoords(raw){
  const match=String(raw||'').match(/^\s*(\d+(?:\.\d+)?)\s*([NS])\s*[,; ]+\s*(\d+(?:\.\d+)?)\s*([EW])\s*$/i);
  if(!match)return null;
  const lat=Number(match[1])*(match[2].toUpperCase()==='S'?-1:1),lon=Number(match[3])*(match[4].toUpperCase()==='W'?-1:1);
  return Math.abs(lat)<=90&&Math.abs(lon)<=180?[lat,lon]:null;
}
export function meaningful(values){return (Array.isArray(values)?values:[values]).filter(v=>v!=null&&!ABSENCE.has(normalize(v))).map(x=>String(x).trim());}
export function wholeMatch(text,option){const term=normalize(option);if(!term)return false;const escaped=term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');return new RegExp(`(^|[^\\p{L}\\p{N}_])${escaped}(?=$|[^\\p{L}\\p{N}_])`,'u').test(normalize(text));}
export function classify(record,loc={}){
  const metadata=record.metadata||{},geo=[...meaningful(metadata.geo_loc_name||[]),...meaningful(metadata.country||[])];
  const rawCoords=meaningful(metadata.lat_lon||[]),coords=rawCoords.map(parseCoords).find(Boolean)||null;
  const places=Object.fromEntries(['countries','states','cities','keywords'].map(key=>[key,terms(loc[key]||[])]));
  const has=Boolean(geo.length||coords),opts=Object.values(places).some(v=>v.length);
  const country=geo[0]?.split(':',1)[0]||'',desc=geo.map(v=>v.includes(':')?v.slice(v.indexOf(':')+1):v).join(' ');
  const matches={
    country:!!country&&places.countries.some(v=>(COUNTRIES[normalize(v)]||normalize(v))===(COUNTRIES[normalize(country)]||normalize(country))),
    state:places.states.some(v=>wholeMatch(desc,STATES[normalize(v)]||v)),
    city:places.cities.some(v=>wholeMatch(desc,v)),
    keyword:places.keywords.some(v=>wholeMatch(desc,v))
  };
  const relevance=!has?'sem localidade':!opts?'não avaliada':matches.keyword?'palavra-chave':matches.city?'cidade':matches.state?'estado':matches.country?'país':'outra localidade';
  return {has_locality:has,locality_origin:geo.length&&coords?'ambos':geo.length?'texto':coords?'coordenadas':'ausente',relevance,matches,coordinates:coords,invalid_coordinates:Boolean(rawCoords.length&&!coords),raw_locality:geo,country_text:country,description:desc,inferred:null};
}
export function summarise(species,records,invalid=[],duplicates=[]){
  const per=new Map(species.map(s=>[s,{species:s,total:0,with_locality:0,without_locality:0,with_coordinates:0}]));
  const found=new Set(),relevance={},localities=new Map(),matrix=new Map();
  for(const r of records){
    const c=r.classification;relevance[c.relevance]=(relevance[c.relevance]||0)+1;
    for(const s of r.species){const row=per.get(s);if(!row)continue;found.add(s);row.total++;row.with_locality+=Number(c.has_locality);row.without_locality+=Number(!c.has_locality);row.with_coordinates+=Number(Boolean(c.coordinates));
      for(const gene of r.genes.length?r.genes:['não filtrado']){const key=JSON.stringify([s,gene,c.relevance]);matrix.set(key,(matrix.get(key)||0)+1);}}
    for(const place of c.raw_locality){if(!localities.has(place))localities.set(place,{name:place,records:0,species:new Set(),origin:['texto']});const row=localities.get(place);row.records++;r.species.forEach(s=>row.species.add(s));}
  }
  const withLocality=records.filter(r=>r.classification.has_locality).length;
  return {submitted:species.length+invalid.length+duplicates.length,valid:species.length,duplicates,invalid,with_records:found.size,without_records:species.filter(s=>!found.has(s)),species_coverage_pct:species.length?Math.round(10000*found.size/species.length)/100:0,total_records:records.length,with_locality:withLocality,without_locality:records.length-withLocality,with_coordinates:records.filter(r=>r.classification.coordinates).length,relevance,species:[...per.values()],localities:[...localities.values()].sort((a,b)=>a.name.localeCompare(b.name)).map(x=>({...x,species:x.species.size})),matrix:[...matrix.entries()].sort(([a],[b])=>a.localeCompare(b)).map(([k,count])=>{const [species,gene,relevance]=JSON.parse(k);return {species,gene,relevance,records:count};})};
}

// GenBank flatfile parser: extracts metadata only, discarding ORIGIN nucleotide sequences.
export function parseGenbank(payload,source={},warn=()=>{}){
  const result={};
  for(const raw of String(payload).split(/^\/\/\s*$/m)){
    const lines=raw.split(/\r?\n/);if(!lines.some(l=>l.startsWith('LOCUS ')))continue;
    try{
      const accession=(lines.find(l=>/^VERSION\s+/.test(l))||'').trim().split(/\s+/)[1]||(lines.find(l=>/^ACCESSION\s+/.test(l))||'').trim().split(/\s+/)[1];
      if(!accession){warn('extração','?','Accession ausente');continue;}
      const organism=(lines.find(l=>/^\s{2}ORGANISM\s+/.test(l))||'').trim().replace(/^ORGANISM\s+/,'');
      const metadata={};let inFeatures=false,inOrigin=false,lastKey=null,openQuote=false;
      for(const line of lines){
        if(line.startsWith('FEATURES ')){inFeatures=true;continue;}
        if(line.startsWith('ORIGIN ')){inOrigin=true;inFeatures=false;break;}
        if(!inFeatures)continue;
        const q=line.match(/^\s{21}\/([a-zA-Z_]+)(?:=(.*))?$/);
        if(q){lastKey=FIELDS.has(q[1])?q[1]:null;openQuote=false;if(!lastKey)continue;
          let value=q[2]??'';openQuote=value.startsWith('"')&&!value.endsWith('"');value=value.replace(/^"/,'').replace(/"$/,'');(metadata[lastKey]??=[]).push(value);continue;}
        if(lastKey&&openQuote&&/^\s{21}\S/.test(line)){
          const part=line.trim();const arr=metadata[lastKey];arr[arr.length-1]+=' '+part.replace(/"$/,'');if(part.endsWith('"'))openQuote=false;
        }
      }
      result[accession]={accession,organism,metadata,species:[...(source[accession]?.species||[])],genes:[...(source[accession]?.genes||[])]};
      if(!organism)warn('extração',accession,'Organismo ausente');
    }catch(e){warn('extração','?',e.message);}
  }
  return result;
}
