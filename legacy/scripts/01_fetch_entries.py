from dotenv import load_dotenv
from Bio import Entrez
from config.settings import ACCESSIONS, ENTRIES
import json, http, os, time

load_dotenv()

Entrez.email = os.getenv("EMAIL")
Entrez.api = os.getenv("API_KEY")
chunk_size = 100

with open(ACCESSIONS) as f:
    data = json.load(f)
    accessions = list(data.keys())

with open(ENTRIES, 'w') as f:
    print(f"fetching {len(accessions)} IDs from accession file")
    for i in range(0, len(accessions), chunk_size):
        chunk = accessions[i : i + chunk_size]
        ids = ",".join(chunk)
        attempts = 0
        success = False
        while attempts < 3 and not success:
            try:
                print(f"fetching chunk {i}-{i+i}")
                with Entrez.efetch(db="nucleotide", id=ids, rettype="gb", retmode="text") as handle:
                    content = handle.read()
                f.write(content)
                success = True
            except (http.client.IncompleteRead, OSError) as e:
                attempts += 1
                print(f"chunk {i}-{i+i}: attempt {attempts} failed ({type(e).__name__})")
                time.sleep(2 * attempts)
        if not success:
            print(f"chunk {i}-{i+i} failed after 3 attempts")