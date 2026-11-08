import test from 'node:test';
import assert from 'node:assert/strict';
import {parseNames,buildQuery,parseCoords,classify,summarise,meaningful,parseGenbank,wholeMatch} from '../src/core.js';

test('normalização, inválidos e duplicados',()=>{
 const x=parseNames(' rhamdia QUELEN, Rhamdia quelen; peixe\nAstyanax lacustris');
 assert.deepEqual(x.valid,['Rhamdia quelen','Astyanax lacustris']);assert.equal(x.duplicates.length,1);assert.deepEqual(x.invalid,['peixe']);
});
test('consulta padrão e avançada',()=>{
 assert.match(buildQuery('Rhamdia quelen','COI'),/COX1/);
 assert.equal(buildQuery('Rhamdia quelen'),'"Rhamdia quelen"[Organism]');
 assert.throws(()=>buildQuery('Rhamdia quelen','','sem marcador'),/especie/);
});
test('coordenadas e valores ausentes',()=>{
 assert.deepEqual(parseCoords('25.5 S 54.6 W'),[-25.5,-54.6]);
 assert.equal(parseCoords('95 N 10 E'),null);
 assert.deepEqual(meaningful(['not collected','Brazil: Paraná']),['Brazil: Paraná']);
});
test('classificação com limite de palavra',()=>{
 const c=classify({metadata:{geo_loc_name:['Brazil: Paraná, Foz do Iguaçu']}},{states:['PR'],keywords:['iguaçu']});
 assert.equal(c.relevance,'palavra-chave');assert.equal(c.matches.state,true);
 assert.equal(wholeMatch('iguaçu','gua'),false);
 assert.equal(classify({metadata:{geo_loc_name:['not collected']}},{}).has_locality,false);
});
test('sumário deduplica registros no total',()=>{
 const records=[{accession:'A.1',species:['Rhamdia quelen','Astyanax lacustris'],genes:['COI'],classification:{has_locality:true,relevance:'país',coordinates:null,raw_locality:['Brazil: Paraná']}}];
 const s=summarise(['Rhamdia quelen','Astyanax lacustris'],records);
 assert.equal(s.total_records,1);assert.equal(s.with_records,2);assert.equal(s.matrix.reduce((x,v)=>x+v.records,0),2);
});
test('parser GenBank extrai metadados sem sequência',()=>{
 const payload=`LOCUS       SAMPLE                  20 bp    DNA     linear   VRT 01-JAN-2024
DEFINITION  Example.
ACCESSION   AB123456
VERSION     AB123456.1
SOURCE      Sample organism
  ORGANISM  Rhamdia quelen
FEATURES             Location/Qualifiers
     source          1..20
                     /organism="Rhamdia quelen"
                     /geo_loc_name="Brazil: Paraná, Foz do Iguaçu"
                     /lat_lon="25.5 S 54.6 W"
ORIGIN
        1 atgcgggttt aaaccggttt
//`;
 const out=parseGenbank(payload,{'AB123456.1':{species:['Rhamdia quelen'],genes:['COI']}});
 assert.deepEqual(out['AB123456.1'].metadata.geo_loc_name,['Brazil: Paraná, Foz do Iguaçu']);
 assert.equal(JSON.stringify(out).includes('atgcgggttt'),false);
});
