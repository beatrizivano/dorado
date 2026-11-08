from config.settings import RECORDS, VALID_NAMES, RECONCILED_TAXONOMY, TAXONOMY_REVISIT
import json

'''
ambíguos: nomes que já foram sinônimos podem ser depósito com nome desatualizado ou se referir a espécie correta de fato

astyanax lacustris
geophagus brasiliensis
hoplias malabaricus
hyphessobrycon boulengeri
imparfinis mirini
pseudopimelodus zungaro
rhamdia branneri
rhamdia quelen

nomes com organismos não presentes no arquivo de nomes válidos vão para o revisit

'''

with open(RECORDS, "r") as r, open(VALID_NAMES, "r") as v:
    records = json.load(r)
    valid_names = json.load(v)  

r = {}
for entry, data in records.items():
    organism = data.get("organism", None)
    alias = valid_names.get(organism, None)
    
    if alias is None:
        print(entry)
        r[entry] = data
    else:
        valid_name = alias.get("valid_name", None)
        if valid_name is None:
            data["ambiguous"] = 1
            data["candidates"] = alias.get("candidates", None).keys()
    
        data["valid_name"] = valid_name

revisit = json.dumps(r)
with open(TAXONOMY_REVISIT, "w") as t, open(RECONCILED_TAXONOMY, "w") as r:
    json.dump(revisit, t, indent=2)
    json.dump(records, r, indent=2)