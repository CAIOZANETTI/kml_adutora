# Gradiente Hidraulico

Aplicacao de pre-dimensionamento de adutoras em Python + Streamlit, com motor numerico vetorizado em NumPy para comparar cenarios de tubos, otimizar solucao por trechos e consolidar alertas hidraulicos a partir de um eixo em KML.

## Arquitetura aplicada

- entrada e organizacao: `geo/` + DataFrame base
- calculo numerico: `hydraulics/` + `transients/` com arrays NumPy
- regras tecnicas e selecao: `optimize/`
- interface e visualizacao: Streamlit + Plotly

Regra central do projeto:

- Pandas organiza
- NumPy calcula
- Plotly mostra
- Streamlit orquestra

## Estrutura principal

- `src/assets/`: catalogo rastreavel de tubos, classes, custos-base e referencias em JSON
- `src/geo/`: leitura KML, estaqueamento, elevacao e perfil
- `src/hydraulics/`: regime permanente vetorizado
- `src/transients/`: envelope preliminar de transientes
- `src/optimize/`: cenarios, zonas, regras tecnicas e workflow
- `src/viz/`: graficos Plotly
- `src/export/`: exportacao para planilhas e CSV
- `app/streamlit_app.py`: interface multipage orientada por `session_state`

## O que a versao atual faz

- importa KML com `LineString`
- discretiza o eixo por estacas
- usa cotas do proprio KML ou consulta o Open-Meteo
- monta um DataFrame base e converte o perfil para arrays NumPy
- testa catalogo de tubos reais em lote
- calcula perdas, gradiente, linha piezometrica e linha de energia por broadcasting
- estima sobrepressao e subpressao com envelope simplificado de Joukowsky
- escolhe um shortlist uniforme e reotimiza por trechos (zonas)
- indica materiais, classes, dispositivos e pontos criticos
- exporta perfil, alternativas, zonas e listas preliminares

## Interface em pages

A interface Streamlit foi reorganizada como fluxo tecnico guiado por etapas:

1. `Tracado`
2. `Diagnostico`
3. `Regime permanente`
4. `Transientes e protecao`
5. `Cenarios de tubulacao`
6. `Solucao final`

Cada etapa usa `st.form`, persiste dados em `st.session_state`, libera a proxima page apenas quando a anterior foi concluida e mostra o log tecnico em `expander` fechado por padrao. Existe ainda uma page auxiliar `Catalogo JSON` para rastreabilidade dos documentos e download dos arquivos-base do app web.

## Catalogo atual

O catalogo em `src/assets/pipe_catalog.json` usa linhas rastreaveis para:

- `PVC-O` em series comerciais tipo BIAX / PN
- `FoFo` em classes de pressao ISO 2531 / C25-C40
- `Aco carbono` em series dimensionais NBR 5590 / ASTM A53 (schedules)

As geometrias e classes seguem series comerciais reais conhecidas. Os custos-base sao tratados como referencias de comparacao tecnico-economica inicial, com origem registrada por linha e data de curadoria no proprio catalogo. A biblioteca de referencias fica em `src/assets/reference_documents.json`.

## Como executar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

Para deploy no Streamlit Community Cloud, use:

- Repository: `CAIOZANETTI/kml_adutora`
- Branch: `main`
- Main file path: `app/streamlit_app.py`

## Testes

```bash
python -m unittest tests/test_core.py
```

## Observacoes tecnicas

- o nucleo hidraulico trabalha preferencialmente com arrays 2D (`cenarios x trechos`)
- a otimizacao por trechos parte de um shortlist uniforme e combina solucoes por zonas hidraulicas
- a camada de transientes ainda e preliminar; serve para triagem e indicacao de protecoes
- os custos nao substituem orcamento executivo nem cotacao comercial

## Base adotada

A organizacao geral do app reaproveita a separacao `app/` + `src/` usada no repositorio [kml-earthworks](https://github.com/CAIOZANETTI/kml-earthworks), mas com o motor numerico completamente refeito para pre-dimensionamento hidraulico vetorizado.
