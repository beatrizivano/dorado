# Dorado

Aplicação web para análise de cobertura de registros genéticos do NCBI. Backend em Node.js (Express) e frontend em HTML/CSS/JavaScript, sem dependência de Python. A base de requisitos é a ERS Dorado v0.1, de 07/11/2026.

## Execução

Requer **Node.js 20 ou superior**.

```bash
npm install
npm start
```

Acesse http://localhost:8000. Para desenvolvimento, execute `npm run dev`. Para testes unitários, `npm test`.

Configure `PORT` e `DORADO_DATA` por variáveis de ambiente, caso necessário. A pasta `data/` é criada automaticamente. A pasta `data/jobs/` guarda histórico e resultados e `data/cache/` guarda apenas metadados, por 30 dias. A chave NCBI recebida para cada execução não é gravada no disco.

## Organização

- `src/server.js`: API HTTP, upload, histórico e exportação.
- `src/core.js`: validação, consulta, interpretação GenBank, classificação e métricas.
- `src/pipeline.js`: integração NCBI, cache e processamento.
- `dorado/static/`: frontend original mantido.
- `tests/`: testes unitários nativos do Node.js.

## Rotas

`POST /api/names`, `POST /api/preview`, `POST /api/upload`, `POST /api/jobs`, `GET /api/jobs`, `GET /api/jobs/:id`, `GET /api/jobs/:id/result`, `POST /api/jobs/:id/cancel`, `POST /api/jobs/:id/duplicate`, `DELETE /api/jobs/:id`, `GET /api/jobs/:id/export/:format` (xlsx, csv ou json).

## Escopo e limitações

A lógica Python foi migrada para JavaScript e os seis scripts legados foram excluídos. A reconciliação taxonômica continua fora do escopo. O parser GenBank implementado é limitado ao formato textual padrão e deve ser comparado a amostras reais antes de ser considerado equivalente ao Biopython.

O sistema **não está homologado** perante a ERS: falta geocodificação reversa offline (RF-19), retomada confiável após reinício do servidor (RF-35/RNF-05), recuperação completa de buscas do NCBI com mais de 10 mil acessions (RF-10), garantias globais de rate-limit para várias análises simultâneas (RNF-03), testes de segurança e carga e outros requisitos avançados. Os testes locais cobrem funções de núcleo; uma consulta real à API NCBI e os endpoints Express não foram validados neste ambiente, pois a instalação das dependências npm não pôde ser concluída.

Não exponha esta versão em rede pública sem implementar controles de acesso, HTTPS, proteção contra abuso e endurecimento dos endpoints. A aplicação não grava sequências nucleotídicas, mas armazena metadados e o e-mail usado na consulta.
