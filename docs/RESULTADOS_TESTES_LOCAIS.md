# Verificação preliminar do desenvolvimento — Dorado

Data de execução: 07/11/2026 (sessão de desenvolvimento).

**Método:** testes unitários automatizados executados no ambiente local, sem acesso ao NCBI. Comando: `python -m pytest -q`.

**Resultado:** 5 testes passaram; 0 falhas observadas.

| Teste | Verificação | Resultado |
|---|---|---|
| `test_names` | Normalização, duplicatas e nomenclatura binomial | Passou |
| `test_queries` | Consultas por gene e sem gene | Passou |
| `test_coords` | Coordenada válida com sinal e latitude inválida | Passou |
| `test_locality` | Palavra-chave, ausência de localidade e correspondência por palavra inteira | Passou |
| `test_summary_consistency` | Consistência entre total e parcelas; espécie sem registro | Passou |

**Escopo da evidência:** os testes validam somente essas unidades de código. Não foram executadas consultas reais ao NCBI, testes end-to-end com grandes volumes, avaliação da geocodificação offline, conformidade de taxa em janelas temporais, exportação real em Excel, reinício forçado, paridade completa com os scripts antigos ou auditorias de segurança e acessibilidade. Não é um relatório da equipe independente de qualidade e não atesta atendimento integral à ERS.

**Defeitos/pendências conhecidos:** listados em `README.md` e `REGISTRO_USO_IA.md`. A equipe de testes deve estabelecer um plano prévio separado e executar os casos de aceitação da ERS.
