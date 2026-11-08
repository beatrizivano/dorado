from config.settings import ENTRIES, ACCESSIONS, RECORDS
from config.params import EXPECTED_QUALIFIERS
from Bio import SeqIO
import json

#ver se references realmente vale estar aqui agora
with open(ACCESSIONS) as f:
    accessions = json.load(f)

with open(ENTRIES, "r") as f:
    for entry in SeqIO.parse(f, "gb"):
        id = entry.id
        organism = entry.annotations.get("organism", None)
        # references = entry.annotations.get("references", None)
        # refs = [] if references is None else [ref.__dict__ for ref in references] 
        
        metadata = {}
        for feature in entry.features:
            for qualifier in feature.qualifiers.keys():
                if qualifier in EXPECTED_QUALIFIERS:
                    data = feature.qualifiers.get(qualifier, None)
                    metadata[qualifier] = data[0]

        accessions[id]["organism"] = organism.lower().strip()
        # accessions[id]["references"] = refs
        accessions[id]["metadata"] = metadata
        
with open(RECORDS, "w") as f:
    json.dump(accessions, f, indent=2)
