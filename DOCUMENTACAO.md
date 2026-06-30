# Documentação Técnica e Metodológica

**Disciplina:** EP101 – Logística (UFPE)
**Trabalho Prático:** Aplicativo e Estudo de Caso
**Última atualização:** 30/06/2026

Este documento descreve, com justificativa, **tudo o que o projeto faz** e **todas as
decisões metodológicas** por trás do código. Está organizado para servir de base direta
à seção *Abordagem metodológica* e *A solução desenvolvida* do relatório.

O projeto é um **aplicativo Streamlit** que aplica métodos quantitativos de apoio à decisão
logística:

| Módulo                       | Problema logístico                                       | Métodos quantitativos                                                     |
| ----------------------------- | --------------------------------------------------------- | -------------------------------------------------------------------------- |
| **Previsão de compra** | Previsão de demanda + decisão de reposição de estoque | Série temporal (Prophet) + EOQ + ROP + Estoque de segurança estatístico |

---

# Parte I — Módulo "Previsão de compra"

**Arquivo:** [`Previsão de compra/app.py`](Previsão%20de%20compra/app.py)
**Estudo de caso:** gestão de categorias de um *seller* parceiro / operação de *fulfillment*,
usando a base pública **Olist** (e-commerce brasileiro, ~100 mil pedidos de 2016–2018).

## 1. Visão geral do fluxo

```
CSVs Olist ─▶ carregar_e_limpar_dados ─▶ série diária por categoria
                                              │
                 ┌────────────────────────────┼───────────────────────────┐
                 ▼                            ▼                            ▼
        get_top_categorias          _preparar_serie_diaria          (entrada do gestor)
        (foco na Curva A)            (calendário contínuo)        lead time, custos, nível
                 │                            │                     de serviço
                 ▼                            ▼
          seleção na UI       ┌── gerar_previsao (Prophet) ──▶ forecast
                              │
                              ├── avaliar_acuracia (backtest) ──▶ MAE / MAPE / WAPE
                              │
                              ▼
            calcular_estoque_seguranca ─▶ calcular_decisao_logistica ─▶ ROP, EOQ
```

## 2. O que já existia (estado original)

### 2.1 Carregamento e limpeza — `carregar_e_limpar_dados`

- **O que faz:** lê três CSVs do Olist (`orders`, `order_items`, `products`), filtra apenas
  pedidos com `order_status = "delivered"`, cruza as três tabelas e agrega as vendas por
  **categoria de produto × dia**, gerando uma série temporal de contagem de itens vendidos.
- **Justificativa das escolhas:**
  - *Filtrar `delivered`* — só pedidos efetivamente entregues representam demanda atendida real;
    pedidos cancelados/indisponíveis distorceriam a previsão.
  - *Agregar por categoria (e não por SKU)* — no nível de SKU a série do Olist é esparsa demais
    (muitos produtos com pouquíssimas vendas), inviabilizando previsão. A categoria é a unidade
    de decisão de compra típica de um gestor de *fulfillment* (decisão por "departamento").
  - *Contagem de linhas de item (`.size()`)* — cada linha de `order_items` é uma unidade vendida,
    então a contagem funciona como **proxy de unidades demandadas**.
  - *`@st.cache_data`* — evita reprocessar os CSVs a cada interação na interface (desempenho).

### 2.2 Foco na Curva A — `get_top_categorias`

- **O que faz:** retorna as `top_n` categorias mais vendidas nos **últimos 30 dias** da base.
- **Justificativa:** princípio de **Curva ABC / Pareto** — concentrar a gestão de estoque nos
  itens de maior giro (Classe A), que respondem pela maior parte do faturamento e do capital
  imobilizado. Usar os últimos 30 dias prioriza relevância **recente**, não histórica.

### 2.3 Previsão — `gerar_previsao` (modelo Prophet)

- **O que faz:** treina o **Prophet** (modelo aditivo de série temporal do Facebook/Meta) com
  sazonalidade **semanal e anual**, e projeta a demanda para o horizonte escolhido (15–90 dias).
  Valores previstos negativos são cortados em zero.
- **Justificativa das escolhas:**
  - *Prophet* — robusto a dados faltantes, lida bem com sazonalidade e tendência sem exigir
    estacionariedade (vantagem sobre ARIMA para um usuário não-estatístico), e produz
    automaticamente **intervalos de incerteza** (`yhat_lower`/`yhat_upper`).
  - *Sazonalidade semanal e anual ligadas, diária desligada* — vendas de e-commerce têm padrão
    forte de dia-da-semana e de época do ano (datas comerciais); sazonalidade *intradiária* não
    existe num dado agregado por dia.
  - *Corte de valores negativos* — demanda física não pode ser negativa; é uma correção de
    coerência sobre a saída do modelo.

### 2.4 Decisão de compra — `calcular_decisao_logistica`

- **O que faz:** a partir da demanda média prevista, calcula:
  - **ROP (Ponto de Pedido):** `ROP = demanda_média_diária × lead_time + estoque_segurança`
  - **EOQ (Lote Econômico de Compra):** `EOQ = √(2 · D · S / H)`, com `D` = demanda anual,
    `S` = custo de emitir pedido, `H` = custo de manter estoque/ano.
- **Justificativa:** são os dois modelos clássicos de **gestão de estoques** (Harris/Wilson para
  o EOQ; modelo de revisão contínua para o ROP). Respondem às duas perguntas gerenciais centrais:
  *"quando comprar?"* (ROP) e *"quanto comprar?"* (EOQ).

### 2.5 Interface — `main_app`

- Painel lateral com parâmetros do gestor (categoria, horizonte, lead time, custos), três
  *cards* de decisão (demanda, ROP, EOQ), interpretação gerencial em texto e gráfico Plotly
  da projeção. **Justificativa:** traduzir o resultado quantitativo em **linguagem de decisão**,
  não apenas números crus — requisito de uma ferramenta de apoio à decisão.

## 3. O que foi feito agora (melhorias e justificativas)

As mudanças atacaram duas lacunas que pesam na avaliação: **ausência de validação do modelo**
e **desconexão entre a previsão e o cálculo de estoque de segurança**.

### 3.1 Refatoração — `_preparar_serie_diaria` (nova função de apoio)

- **O que mudou:** a montagem da série temporal diária (preencher dias sem venda com 0, criar a
  coluna `y_real` da demanda real e a coluna `y` suavizada por **média móvel de 7 dias**) foi
  extraída para uma função única, reutilizada tanto pela previsão quanto pelo backtest.
- **Justificativa:**
  - *Calendário contínuo* — o Prophet exige uma linha por dia; dias sem venda precisam ser 0
    explícito, senão o modelo "pula" buracos e distorce a sazonalidade.
  - *Média móvel de 7 dias no treino* — a demanda diária do Olist é **intermitente** (muitos dias
    com 0 e picos isolados); suavizar reduz o ruído e estabiliza o ajuste, sem perder a tendência.
    O dado **real** é preservado em `y_real` para o gráfico e para a avaliação honesta do erro.
  - *Eliminar duplicação* — previsão e backtest passam a usar **exatamente** a mesma preparação,
    garantindo que a métrica de erro reflita o modelo que de fato é usado (e é mais fácil de
    explicar na banca).

### 3.2 Validação do modelo — `avaliar_acuracia` (backtest) ⭐

- **O que faz:** esconde os **últimos 30 dias** da série, treina o Prophet **somente com o
  passado** e compara a previsão contra a demanda real escondida. Calcula três métricas de erro e
  ainda compara o modelo com uma **previsão ingênua (baseline)**:
  - **WAPE** (Erro Percentual Ponderado) — erro absoluto total ÷ volume total. **É a métrica
    principal** exibida no card.
  - **MAE** (Erro Médio Absoluto) — quantas unidades/dia o modelo erra, em média.
  - **MAPE** (Erro Percentual Médio Absoluto) — mostrado apenas como rodapé (ver justificativa).
  - **Baseline ingênua** — prever todo dia como a **média histórica** de vendas; o modelo só "vale
    a pena" se errar menos que isso. A interface mostra a **melhora percentual** do modelo sobre a
    baseline (verde se supera, amarelo se não supera).
- **Justificativa:**
  - *Por que validar* — apresentar previsões sem medir o erro não tem valor gerencial; a primeira
    pergunta de qualquer decisor (e da banca) é *"como sabemos que essa previsão acerta?"*. O
    backtest é a evidência exigida pela seção **Resultados e discussão** do enunciado.
  - *Por que treino/teste com o passado* — simula a situação real: prever o futuro só com o que se
    conhecia até o momento, sem "espiar" o resultado (evita *data leakage*).
  - *Por que o WAPE é a métrica principal (e o MAPE foi rebaixado)* — o MAPE é intuitivo (%), mas
    **explode em demanda diária intermitente**: dias de venda baixa fazem a divisão estourar
    (chegou a passar de 200% em categorias de presente). Isso é um artefato da métrica, não do
    modelo, e dá uma impressão falsa de desastre. O **WAPE** mede o erro sobre o volume total e não
    sofre desse problema, sendo a leitura honesta. O MAE complementa com a magnitude em unidades.
  - *Por que comparar com uma baseline* — um número de erro isolado não é "bom" nem "ruim"; ele só
    significa algo **comparado a fazer o simples**. Mostrar *"WAPE 37% do modelo vs. 50% da média"*
    prova que o modelo agrega valor — e, quando **não** supera (categorias muito sazonais), a
    própria ferramenta admite isso e orienta a confiar mais no estoque de segurança. É a transparência
    que a banca valoriza.
  - *Salvaguarda* — se a categoria tem histórico curto (≤ ~60 dias), a função retorna `None` e a
    interface avisa, em vez de exibir uma métrica não confiável.

### 3.3 Estoque de segurança estatístico — `calcular_estoque_seguranca` ⭐

- **O que faz:** substitui o valor fixo "chutado" pelo cálculo clássico:
  **`SS = z × σ_demanda_diária × √lead_time`**, onde `σ` é o desvio-padrão **real** da demanda
  diária da categoria e `z` vem do **nível de serviço** escolhido (80–99%), via tabela da Normal
  padrão (`Z_NIVEL_SERVICO`).
- **Justificativa:**
  - *Por que estatístico* — o estoque de segurança existe para absorver a **variabilidade** da
    demanda durante o lead time. Defini-lo como número fixo ignora justamente essa variabilidade;
    a fórmula a incorpora explicitamente, conectando **a previsão à decisão de estoque** (antes os
    dois módulos do app estavam desconectados).
  - *Por que `√lead_time`* — a variabilidade acumulada durante o lead time cresce com a raiz do
    número de dias (soma de variâncias de dias independentes), resultado padrão da teoria de
    estoques.
  - *Por que nível de serviço configurável* — expõe o **trade-off gerencial** central: maior nível
    de serviço (menor risco de ruptura) ⇒ maior `z` ⇒ mais estoque imobilizado. Verificado: o SS
    cresce de forma coerente (≈25 unid. a 80% → ≈50 a 95% → ≈71 a 99% para uma categoria típica).
  - *Por que tabela de `z` fixa em vez de `scipy`* — evita uma dependência extra e mantém o cálculo
    transparente e fácil de explicar (cada valor de `z` é um ponto conhecido da curva Normal).
  - *Transparência na UI* — a interface mostra a conta aberta (`z`, `σ`, lead time), reforçando que
    o número não é arbitrário. O método **Manual** continua disponível como alternativa.

### 3.4 Integração na interface

- A barra lateral passou a permitir escolher **Estoque de Segurança: Estatístico × Manual**.
- Após gerar a análise, surgem duas novas seções: **"🎯 Confiabilidade da Previsão (Backtest)"**
  (com MAE/MAPE/WAPE) e a legenda do **estoque de segurança** com o cálculo detalhado.

## 4. Verificação realizada

- `python -m py_compile app.py` → **OK** (sintaxe válida).
- *Smoke test* com o dataset real (18.808 registros / 714 dias): carregamento, Curva A, cálculo de
  σ, EOQ/ROP e estoque de segurança rodaram corretamente; o ROP fecha a conta (`5×7 + 50 = 85`) e
  o SS escala certo com o nível de serviço.
- **Ressalva:** as funções que dependem do **Prophet** (`gerar_previsao`, `avaliar_acuracia`) não
  foram executadas ao vivo no ambiente de desenvolvimento (Prophet não instalado); recomenda-se
  rodar uma vez localmente com o venv do projeto antes da apresentação.

## 5. Limitações conhecidas (para a seção "Resultados e discussão")

- A base Olist termina em ~2018; "últimos 30 dias" é relativo ao **histórico**, não a tempo real.
- A demanda anual do EOQ é estimada anualizando a média do horizonte (`média × 365`), o que
  **suaviza a sazonalidade** que o Prophet captura — premissa a declarar no relatório.
- A contagem de itens é **proxy** de unidades; não distingue múltiplas unidades do mesmo item num
  pedido com precisão de quantidade.
- O modelo trata cada categoria isoladamente (sem efeitos cruzados entre categorias).

---

# Parte II — Extensões futuras sugeridas

- **Lote de segurança dinâmico:** usar a incerteza do próprio Prophet (`yhat_upper`) como entrada
  alternativa para o σ do estoque de segurança.
- **Validação cruzada temporal** (vários cortes de backtest) em vez de um único hold-out, para uma
  estimativa de erro mais estável.

---

# Parte III — Como executar

Instruções completas de instalação e execução estão no [`README.md`](README.md). Resumo:

```bash
# ambiente virtual + dependências
python -m venv venv
.\venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt

# rodar o módulo
streamlit run "Previsão de compra/app.py"
```
