# Dorado — diagnóstico de cobertura genética e geográfica

Evolução experimental do pipeline Python 00–05 em um **serviço HTTP FastAPI + interface web**. Base de requisitos: *Especificação de Requisitos de Sistema — Dorado*, v0.1, 07/11/2026. A interface segue referências gerais do estilo **Swiss Minimalist**: tipografia expressiva, grades rígidas, contraste preto/branco, acento verde-lima e poucos ornamentos.

## Instalação

```bash
python -m venv .venv
# Ative o ambiente virtual conforme seu sistema operacional
pip install -r requirements.txt
python run.py
```

Abra `http://127.0.0.1:8000`. Informe e-mail válido de contato para identificação junto ao NCBI. A chave de API é opcional. Os dados de análises e cache ficam em `data/`. A aplicação não armazena sequências nucleotídicas, apenas metadados. Não publique esta versão diretamente na internet sem hardening, autenticação de administração, HTTPS e revisão de segurança.

## Fluxo implementado

1. Colar/importar lista de espécies; escolher aba e coluna de CSV/XLSX; validar e normalizar nomes.
2. Definir genes, localidades e opcionalmente consulta avançada com `{especie}` e `{gene}`.
3. Informar contato NCBI, iniciar trabalho em thread e acompanhar no histórico.
4. Buscar accession via esearch paginado, fazer download em lotes, extrair qualificadores, classificar presença e relevância e calcular agregados.
5. Consultar painel e exportar JSON/CSV/XLSX (cinco abas).

## Limitações conhecidas / lacunas da ERS

**Esta é uma implementação parcial, não a entrega completa e homologada da ERS.** O processamento utiliza um serviço Python, opção permitida para módulos encapsulados em API, mas diferente da preferência pela pilha JavaScript (seção 2.4). A geocodificação reversa offline **não foi implementada**: coordenadas válidas são reconhecidas e contadas, porém país/estado/cidade não são inferidos (RF-19, RN-06/RN-07 parcialmente). A API esearch pode impor limites específicos de paginação mesmo com `retstart`; divergências de contagem são avisadas, não solucionadas de forma garantida (RF-10 parcial). A retomada fina dos lotes falhos, reinício automático após reinício do servidor e execução realmente durável são **pendências** (RF-12/35, RNF-05). O cache atual é baseado no accession retornado pela busca e não assegura uma chave `accession.version` em todos os casos. Falta atualização de progresso por SSE/WebSocket, cálculo de tempo restante, execução concorrente controlada, limites de volume, mapa, predefinições, filtro completo de todas as tabelas, links individuais NCBI e medidas de segurança/privacidade para publicação. A implementação ainda requer testes externos com NCBI, testes de carga, acessibilidade, segurança e testes de paridade para avaliar RNF-13. Não há reconciliação taxonômica, conforme exclusão expressa da ERS.

`python -m pytest -q` executa testes unitários locais independentes de rede. Credenciais e sequências não são registradas em `config.json`; exportações e histórico armazenam e-mail de contato, e exigem revisão de privacidade antes de publicar.

Consulte `docs/REGISTRO_USO_IA.md` para o registro acadêmico das entradas, solicitações e ressalvas de utilização de IA.
