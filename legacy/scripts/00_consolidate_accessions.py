import csv
import requests
from config.settings import QUERIES, ACCESSIONS
from config.params import GENE_QUERIES
import os
from dotenv import load_dotenv
from collections import defaultdict
import json

load_dotenv()

queries = {}
for file_path in QUERIES.iterdir():
    if file_path.is_file():
        river = file_path.stem
        with file_path.open("r", encoding="utf-8") as file:
            query = file.read()

            for gene, geneQuery in GENE_QUERIES.items():
                queries.setdefault(river, {})[gene] = query + geneQuery

url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

params = {
    "email": os.getenv("EMAIL"),
    "apikey": os.getenv("API_KEY"),
    "retmax": 1000000000,
    "db": "nucleotide",
    "retmode": "json",
    "idtype": "acc"
}

records = defaultdict(lambda: { "genes": set(), "rivers": set() })
for river, genes in queries.items():
    for gene, query in genes.items():
        req = requests.post(url, data=params | { "term": query })
        res = req.json().get("esearchresult")
        ids = res.get("idlist", None)

        if ids is not None:
            for id in ids:
                records[id]["genes"].add(gene)
                records[id]["rivers"].add(river)

out = {
    acc: {"genes": sorted(v["genes"]), "rivers": sorted(v["rivers"])}
    for acc, v in records.items()
}        

with open(ACCESSIONS, 'w') as f:
    json.dump(out, f, indent=2)
