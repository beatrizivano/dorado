import pandas as pd
from config.settings import RELIABILITY_CLASS, SUMMARY

df = pd.read_csv(RELIABILITY_CLASS)
gene = df.groupby(["valid_name", "gene"]).size().unstack(fill_value=0)
category = df["relevance"]

highest = category == "highest"
high = category == "high"
medium = category == "medium"
low = category == "low"
unknown = df["reliability"] == "low"

relevance = pd.DataFrame({
    "Total de registros": df.groupby("valid_name").size(),
    "Consta Rio Iguaçu": df[highest].groupby("valid_name").size(),
    "Consta cidades banhadas pelo Iguaçu ou estado do Paraná": df[high].groupby("valid_name").size(),
    "Consta Brasil": df[medium].groupby("valid_name").size(),
    "Consta outros países": df[low].groupby("valid_name").size(),
    "Sem localidade": df[unknown].groupby("valid_name").size()
}).fillna(0).astype(int)

detailed = gene.join(relevance)
detailed.index.name = "Espécie"

species_amount = df["valid_name"].nunique()
percentage = (species_amount / 125) * 100

summary = pd.Series({
    "Quantidade de registros": len(df),
    "Espécies encontradas": f"{species_amount}/125 - {percentage:.1f}%",
    "Sem localidade": unknown.sum(),
    "Baixa relevância (localidade informa outros países)": low.sum(),
    "Média relevância (localidade informa apenas Brasil)": medium.sum(),
    "Alta relevância (localidade informa cidades banhadas pelo Iguaçu ou estado do Paraná)": high.sum(),
    "Altíssima relevância (localidade informa Rio Iguaçu)": highest.sum(),
})

with pd.ExcelWriter(SUMMARY, engine='xlsxwriter') as writer:
    detailed.to_excel(writer, sheet_name='Sheet1')
    summary.to_excel(writer, sheet_name='Sheet2')