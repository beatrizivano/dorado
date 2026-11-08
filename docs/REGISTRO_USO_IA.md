# Registro do desenvolvimento assistido por IA — Dorado

**Objetivo:** registrar quais materiais foram entregues à IA, quais operações foram solicitadas e quais artefatos resultaram. Este documento **não reproduz os prompts literais**. É um registro retrospectivo do trabalho produzido nesta interação, não a transcrição de uma sequência de prompts distinta nem comprovação de execução em outros modelos.

## 1. Contexto fornecido

| Entrada | Conteúdo usado | Finalidade |
|---|---|---|
| Enunciado do trabalho interdisciplinar | Orientações de Meio Ambiente e Desenvolvimento e Qualidade de Software, incluindo separação de equipes, registro das interações com IA e entregas | Delimitar processo, documentação e rastreabilidade |
| ERS Dorado v0.1 (07/11/2026) | Escopo, RF/RNF, regras RN, casos de uso, critérios de aceitação e análise de legado (Anexo A) | Referência normativa e funcional prioritária |
| `scripts.zip` | Scripts Python 00–05 do pipeline anterior | Identificação das entradas/saídas, regras anteriores e inconsistências |
| `settings.py` | Diretórios e caminhos para arquivos raw, interim e final | Compreender a organização do legado |
| `params.py` | Genes/sinônimos e listas de localidades | Compreender os parâmetros antes fixos |
| Página de referência visual | URL `https://designprompts.dev/?style=swiss-minimalist&width=wide&section=hero` | Direcionar o estilo geral da interface; o acesso automático à página específica não foi concluído |

## 2. Pedidos dirigidos à IA por etapa

| Etapa | Parâmetros / entradas informados à IA | O que foi solicitado | Saídas geradas nesta versão |
|---|---|---|---|
| Levantamento e leitura | Scripts legados, configurações e ERS | Entender o comportamento existente e tratar Dorado como evolução do legado | Diagnóstico das incompatibilidades e delimitação de escopo no README |
| Arquitetura | ERS, necessidade de aplicação web e arquivos Python existentes | Transformar scripts isolados em pipeline acionado por interface e API | `dorado/core.py`, `dorado/api.py`, `run.py` |
| Entrada de espécies | RF-01 a RF-03, planilhas CSV/XLSX e campo de texto | Receber nomes, validar, normalizar, eliminar duplicatas e permitir importação | API `/api/names`, `/api/upload` e formulário web |
| Busca genética | RF-04, RF-06, RF-10, RF-11; genes COI/12S/16S e NCBI E-utilities | Montar consultas por espécie/gene, preservar proveniência, paginar e respeitar espera | `build_query`, `run_pipeline` (busca), `/api/preview` |
| Download e extração | Scripts 01/02, RF-12 a RF-15 e qualificadores GenBank | Substituir as etapas de download e leitura, tolerando falhas e preservando múltiplos valores | Rotinas em `core.py` com lotes, tentativas, cache e extração |
| Classificação | Script 04, RF-16 a RF-23, RN-03 a RN-07 | Classificar presença e nível de correspondência textual segundo parâmetros informados | `parse_coords`, `classify`, avisos de coordenadas inválidas; geocodificação offline pendente |
| Síntese | Script 05, RF-24 a RF-30 e RN-09 | Substituir denominador fixo e calcular cobertura e distribuição por espécie, gene e localidade | `summarise`, painel, exportações XLSX/CSV/JSON |
| Interface gráfica | ERS seção 3.3 e modelo visual Swiss Minimalist | Construir interface web em português, com hierarquia tipográfica marcante, poucos ornamentos e visual responsivo | `static/index.html`, `styles.css`, `app.js` |
| Testes locais | Exemplos explícitos de aceitação RF-03, RF-04, RF-16, RF-18, RF-20, RF-24/25 | Criar e executar testes unitários sem depender de consultas reais ao NCBI | `tests/test_core.py` e resultados do pytest (consultar `docs/RESULTADOS_TESTES_LOCAIS.md`) |
| Documentação | Enunciado acadêmico + ERS | Registrar entradas/solicitações em vez do texto exato dos prompts; documentar limites | Este arquivo, README e relatório de testes |

## 3. Uso, divisão de responsabilidades e rastreabilidade

- **Modelo utilizado nesta interação:** ChatGPT / GPT-6 para leitura e análise, produção inicial do código, interface e documentos.
- **Papel da IA:** desenvolvimento de uma primeira versão e elaboração do registro técnico.
- **Papel da equipe de requisitos:** autora do documento ERS fornecido; esta interação não verifica o processo de aprovação do documento.
- **Papel da equipe de testes:** deverá ser separado do desenvolvimento, conforme enunciado. Os testes unitários automatizados que acompanham o repositório são verificações técnicas preliminares do desenvolvimento **e não substituem o plano de testes prévio elaborado pela equipe de testes**.
- **Limitações de registro:** não houve captura de prompts alternativos, iterações com diferentes LLMs ou experimentos comparativos nesta implementação. Não atribuir etapas a modelos que não foram usados.

## 4. Mudanças relevantes em relação ao legado

1. Etapa 00: buscas geradas de parâmetros da interface, por espécie × gene, com contagem e paginação; salva proveniência.
2. Etapa 01: download por lote, retentativas e cache de metadados; não armazena a sequência bruta.
3. Etapa 02: extração tolerante à ausência de organismo e com preservação de múltiplos valores.
4. Etapa 03: **removida do fluxo**, por exclusão da reconciliação taxonômica no escopo da ERS.
5. Etapa 04: classificação textual parametrizável, validação de coordenadas e classificação de presença; geocodificação reversa pendente.
6. Etapa 05: resumo derivado das espécies efetivamente fornecidas e exportação em cinco abas; não usa o total fixo de 125 espécies.

## 5. Pendências, não conformidades e orientações para testes independentes

- Verificar toda a matriz de rastreabilidade do documento ERS, não apenas os casos unitários implementados.
- Exercitar consultas reais no NCBI com uma lista pequena e registrar erros, duração e contagens.
- Avaliar dados de coordenadas em geocodificação offline (RF-19) e ambiguidade de topônimos.
- Testar retomada de lotes, reinício do servidor, persistência de jobs e concorrência (RF-35/RNF-05).
- Validar exportações, proteção de fórmulas, privacidade, navegadores, acessibilidade e desempenho em volume.
- Examinar a paridade com um conjunto de dados fixo do pipeline anterior, documentando diferenças previstas no Anexo A.

**Observação:** o enunciado solicita também documentos separados de plano e relatório de testes e slides. Este registro não equivale a esses documentos, e os resultados preliminares do desenvolvedor não devem ser apresentados como testes independentes da equipe responsável.
