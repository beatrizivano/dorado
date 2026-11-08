from dorado.core import parse_names,build_query,parse_coords,classify,summarise,meaningful

def test_names():
    d=parse_names(' rhamdia QUELEN, Rhamdia quelen; peixe\nAstyanax lacustris')
    assert d['valid']==['Rhamdia quelen','Astyanax lacustris']
    assert len(d['duplicates'])==1 and d['invalid']==['peixe']

def test_queries():
    assert 'COX1' in build_query('Rhamdia quelen','COI')
    assert '[Organism]' in build_query('Rhamdia quelen')

def test_coords():
    assert parse_coords('25.5 S 54.6 W')==(-25.5,-54.6)
    assert parse_coords('95 N 10 E') is None

def test_locality():
    loc={'countries':['Brasil'],'states':['Paraná'],'keywords':['iguaçu']}
    r={'metadata':{'geo_loc_name':['Brazil: Paraná, Foz do Iguaçu']}}
    c=classify(r,loc)
    assert c['has_locality'] and c['relevance']=='palavra-chave'
    assert not classify({'metadata':{'geo_loc_name':['not collected']}},loc)['has_locality']
    assert classify({'metadata':{'geo_loc_name':['Brazil: Paraguai']}},{'keywords':['gua']})['relevance']=='outra localidade'

def test_summary_consistency():
    r={'accession':'A.1','species':['Rhamdia quelen'],'genes':['COI'],
       'classification':classify({'metadata':{'geo_loc_name':['Brazil: Paraná']}},{'states':['Paraná']})}
    x=summarise(['Rhamdia quelen','Astyanax lacustris'],[r],{})
    assert x['total_records']==x['with_locality']+x['without_locality']
    assert x['without_records']==['Astyanax lacustris']
