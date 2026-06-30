<div align="center">

# Universidade Federal de Pernambuco
## EP101 – Logística

<br>

# Trabalho Prático: Aplicativo e Estudo de Caso

### Sistema de Previsão de Demanda e Gestão de Estoques para um *Seller* de E-commerce

<br><br>

**Integrantes do grupo:**

Victor Matias
Peterson Melo
Gabriel Nóbrega
Adna Farias

<br><br>

**Professor:** João Mateus

**Data de entrega e apresentação:** 30/06/2026

</div>

<div style="page-break-after: always;"></div>

## Sumário

1. [Contextualização e motivação](#1-contextualização-e-motivação)
2. [O estudo de caso](#2-o-estudo-de-caso)
3. [Abordagem metodológica](#3-abordagem-metodológica)
4. [A solução desenvolvida](#4-a-solução-desenvolvida)
5. [Resultados e discussão](#5-resultados-e-discussão)
6. [Considerações finais](#6-considerações-finais)
7. [Referências](#7-referências)

<div style="page-break-after: always;"></div>

## 1. Contextualização e motivação

### 1.1 O contexto logístico

A gestão de estoques é um dos pilares da logística empresarial e está diretamente ligada
ao equilíbrio entre dois custos opostos: o **custo de manter estoque** (capital imobilizado,
armazenagem, obsolescência) e o **custo de ruptura** (vendas perdidas, insatisfação do cliente,
penalidades de nível de serviço). Decidir *quanto* e *quando* comprar é, portanto, uma decisão
recorrente e de alto impacto financeiro para qualquer operação que movimente produtos físicos.

No comércio eletrônico, esse desafio é amplificado. Um *seller* parceiro de um *marketplace* —
ou uma operação de *fulfillment* — lida com centenas de categorias de produtos, cada uma com seu
próprio padrão de demanda, sazonalidade e variabilidade. Comprar em excesso significa imobilizar
capital em mercadoria parada; comprar de menos significa perder a venda para o concorrente em
poucos cliques. A decisão precisa ser tomada com frequência e, idealmente, apoiada em dados.

### 1.2 Relevância do problema

A maior parte das pequenas e médias operações de e-commerce ainda decide reposição de estoque de
forma **intuitiva** ("vamos comprar o mesmo do mês passado") ou reativa (compra-se quando o estoque
"parece baixo"). Essa abordagem ignora dois elementos centrais que a teoria de estoques formaliza:

- a **previsão da demanda futura**, que deveria orientar o volume de compra; e
- a **variabilidade da demanda**, que deveria dimensionar a proteção contra rupturas
  (o estoque de segurança).

Uma ferramenta que automatize essa análise — partindo do histórico de vendas e produzindo
recomendações de compra explicáveis — tem valor gerencial direto: reduz capital imobilizado,
diminui rupturas e transforma uma decisão subjetiva em uma decisão baseada em evidência.

### 1.3 Objetivos do trabalho

O objetivo geral é **desenvolver um aplicativo funcional de apoio à decisão** que, a partir do
histórico real de vendas de um e-commerce, responda às duas perguntas centrais da gestão de
estoques — *quando comprar?* e *quanto comprar?* — para as categorias de maior giro.

Os objetivos específicos são:

1. Tratar e estruturar dados públicos reais de e-commerce em uma série temporal de demanda diária
   por categoria de produto;
2. Aplicar um **modelo de previsão de demanda** (série temporal) adequado a dados intermitentes;
3. Traduzir a previsão em uma **decisão de compra** por meio dos modelos clássicos de gestão de
   estoques — Ponto de Pedido (ROP), Lote Econômico de Compra (EOQ) e estoque de segurança
   estatístico;
4. **Validar a confiabilidade** do modelo de previsão por meio de *backtest*, expondo métricas de
   erro ao usuário;
5. Entregar tudo isso em uma **interface interativa** que comunique os resultados em linguagem de
   decisão gerencial, não apenas em números crus.

<div style="page-break-after: always;"></div>

## 2. O estudo de caso

### 2.1 A empresa e a "roupagem" do caso

O aplicativo foi construído sobre a *roupagem* de um ***seller* parceiro de um grande *marketplace*
brasileiro**, atuando em regime de *fulfillment* (o *marketplace* armazena e expede os produtos do
*seller*). Esse é um perfil de empresa muito comum no e-commerce nacional — semelhante a vendedores
que operam dentro de plataformas como Mercado Livre, Amazon ou Magalu.

Nesse modelo de negócio, o gestor toma decisões de reposição **por categoria/departamento** (e não
produto a produto), pois o sortimento é grande e o reabastecimento é planejado em nível agregado.
A pergunta de negócio é, então: *"para cada departamento de maior giro, quanto e quando devo enviar
ao centro de distribuição do marketplace para não romper o estoque nem imobilizar capital?"*

### 2.2 Origem dos dados

Como base concreta, foi utilizado o **Brazilian E-Commerce Public Dataset by Olist**, um conjunto de
dados **público e real** disponibilizado no Kaggle. Ele contém aproximadamente **100 mil pedidos**
realizados entre **2016 e 2018** em múltiplos *marketplaces* brasileiros, com informações anonimizadas
de pedidos, itens, produtos, clientes, pagamentos e avaliações.

Dos nove arquivos do dataset, o aplicativo utiliza três:

| Arquivo | Conteúdo utilizado |
| --- | --- |
| `olist_orders_dataset.csv` | Identificação do pedido, *status* e data da compra |
| `olist_order_items_dataset.csv` | Itens de cada pedido (cada linha = uma unidade vendida) |
| `olist_products_dataset.csv` | Categoria de cada produto |

### 2.3 Tratamento dos dados

O pré-processamento aplicado segue uma sequência de decisões justificadas:

1. **Filtro de pedidos entregues** — mantêm-se apenas pedidos com `order_status = "delivered"`.
   Apenas pedidos efetivamente entregues representam demanda atendida real; pedidos cancelados ou
   indisponíveis distorceriam a estimativa de demanda.
2. **Cruzamento das tabelas** — os itens são unidos aos pedidos (para obter a data da compra) e aos
   produtos (para obter a categoria).
3. **Agregação por categoria × dia** — as vendas são contadas por categoria de produto e por dia,
   gerando a série temporal de demanda. A contagem de linhas de item funciona como **proxy de
   unidades demandadas**.
4. **Calendário contínuo** — para cada categoria, dias sem nenhuma venda são preenchidos com zero,
   pois o modelo de previsão exige uma observação por dia (sem "buracos" de calendário).

### 2.4 Premissas adotadas

Como todo estudo de caso que combina dados reais com a operação de uma empresa fictícia, algumas
premissas foram explicitadas:

- **A categoria é a unidade de decisão de compra.** No nível de produto individual (SKU), a série
  do Olist é esparsa demais para previsão confiável; a categoria reflete a decisão real de um gestor
  de *fulfillment*.
- **A contagem de itens é proxy de unidades.** Não se distingue, com precisão, a quantidade de
  unidades idênticas dentro de um mesmo pedido.
- **Parâmetros de custo e lead time são fornecidos pelo gestor** na interface (custo de pedido,
  custo de manter estoque, lead time do fornecedor, nível de serviço), pois esses valores dependem
  da operação específica e não estão no dataset. São, portanto, valores configuráveis e verossímeis.
- **O "presente" é relativo ao histórico.** Como a base termina em 2018, expressões como
  "últimos 30 dias" referem-se ao fim do histórico disponível, não à data atual.

<div style="page-break-after: always;"></div>

## 3. Abordagem metodológica

A solução combina **um método de previsão** com **três modelos clássicos de gestão de estoques**,
integrados em um único fluxo de decisão.

### 3.1 Curva ABC (Pareto) — foco nos itens certos

Antes de prever, o aplicativo seleciona as **10 categorias de maior giro nos últimos 30 dias** da
base. Essa escolha aplica o princípio da **Curva ABC / Pareto**: concentrar o esforço de gestão de
estoque nos itens da Classe A, que respondem pela maior parte do faturamento e do capital
imobilizado. Usar a janela recente prioriza relevância atual, não histórica.

### 3.2 Previsão de demanda — modelo Prophet

A demanda futura de cada categoria é prevista com o **Prophet**, um modelo aditivo de série temporal
desenvolvido pela Meta (Facebook). O Prophet decompõe a série em **tendência + sazonalidade +
componente de feriados**, e foi configurado com sazonalidade **semanal e anual** ativas e diária
desativada.

Justificativa da escolha:

- **Robustez a dados intermitentes e faltantes.** A demanda diária por categoria no Olist tem muitos
  dias com zero e picos isolados; o Prophet lida bem com isso sem exigir estacionariedade, o que o
  torna mais adequado que ARIMA para um usuário não-estatístico.
- **Sazonalidade explícita.** Vendas de e-commerce têm forte padrão de dia-da-semana e de época do
  ano (datas comerciais); essas sazonalidades são justamente o que o modelo captura. Não há
  sazonalidade *intradiária* em um dado agregado por dia, por isso ela é desativada.
- **Intervalos de incerteza automáticos.** O Prophet fornece `yhat_lower` e `yhat_upper`, úteis para
  comunicar a confiança da previsão.

Como tratamento adicional, a série usada no **treino** é suavizada por uma **média móvel de 7 dias**,
para reduzir o ruído da intermitência, enquanto a **demanda real** é preservada para a avaliação de
erro e para os gráficos. Valores previstos negativos são cortados em zero, pois demanda física não
pode ser negativa.

### 3.3 Decisão de compra — ROP, EOQ e estoque de segurança

A previsão alimenta três fórmulas clássicas de gestão de estoques:

**Ponto de Pedido (ROP — *Reorder Point*):**

$$ ROP = (\bar{d} \times L) + SS $$

onde $\bar{d}$ é a demanda média diária prevista, $L$ é o *lead time* do fornecedor (em dias) e
$SS$ é o estoque de segurança. O ROP responde *"quando comprar?"*: quando o estoque atinge esse
nível, é hora de emitir novo pedido.

**Lote Econômico de Compra (EOQ — modelo de Harris/Wilson):**

$$ EOQ = \sqrt{\frac{2 \cdot D \cdot S}{H}} $$

onde $D$ é a demanda anual estimada, $S$ é o custo de emitir um pedido e $H$ é o custo de manter uma
unidade em estoque por ano. O EOQ responde *"quanto comprar?"*: o tamanho de lote que minimiza a soma
dos custos de pedido e de manutenção.

**Estoque de segurança estatístico:**

$$ SS = z \times \sigma_d \times \sqrt{L} $$

onde $z$ é o fator da distribuição Normal padrão associado ao **nível de serviço** desejado
(80% a 99%), $\sigma_d$ é o desvio-padrão **real** da demanda diária da categoria e $L$ é o lead
time. Essa formulação:

- conecta a **variabilidade real da demanda** à proteção contra ruptura (em vez de adotar um valor
  fixo arbitrário);
- usa $\sqrt{L}$ porque a variabilidade acumulada ao longo do lead time cresce com a raiz do número
  de dias (soma de variâncias de dias independentes), resultado padrão da teoria de estoques;
- expõe o **trade-off gerencial** central: maior nível de serviço ⇒ maior $z$ ⇒ mais estoque
  imobilizado.

O fator $z$ é obtido de uma tabela fixa da Normal padrão, evitando uma dependência externa e mantendo
o cálculo transparente:

| Nível de serviço | 80% | 85% | 90% | 95% | 97% | 99% |
| --- | --- | --- | --- | --- | --- | --- |
| Fator $z$ | 0,84 | 1,04 | 1,28 | 1,65 | 1,88 | 2,33 |

### 3.4 Validação do modelo — *backtest*

Para que a previsão tenha valor gerencial, é preciso medir seu erro. O aplicativo realiza um
***backtest* (validação histórica)**: esconde os **últimos 30 dias** da série, treina o Prophet
**somente com o passado** e compara a previsão contra a demanda real escondida. Isso simula a
situação real de decisão e evita *data leakage* (não se "espia" o futuro). São reportadas três
métricas complementares:

- **MAE (Erro Médio Absoluto)** — quantas unidades/dia o modelo erra, em média (magnitude absoluta).
- **MAPE (Erro Percentual Médio Absoluto)** — erro percentual, calculado **apenas nos dias com
  venda** para evitar divisão por zero.
- **WAPE (Erro Percentual Ponderado)** — erro absoluto total dividido pelo volume total; é a métrica
  mais honesta para demanda intermitente, pois não "explode" em dias com demanda zero.

### 3.5 Ferramentas utilizadas

| Ferramenta | Função |
| --- | --- |
| **Python 3.8+** | Linguagem base |
| **Streamlit** | Interface web interativa |
| **pandas** | Leitura, limpeza e estruturação da série temporal |
| **Prophet** | Modelo de previsão de demanda |
| **Plotly** | Gráfico interativo da projeção |

<div style="page-break-after: always;"></div>

## 4. A solução desenvolvida

### 4.1 Arquitetura

O aplicativo é um único módulo Streamlit ([`Previsão de compra/app.py`](Previsão%20de%20compra/app.py))
organizado em funções com responsabilidade única, seguindo o fluxo abaixo:

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

Cada função tem papel claro:

| Função | Responsabilidade |
| --- | --- |
| `carregar_e_limpar_dados` | Lê os CSVs, filtra pedidos entregues, cruza tabelas e agrega vendas por categoria × dia |
| `get_top_categorias` | Seleciona as categorias da Curva A (maior giro recente) |
| `_preparar_serie_diaria` | Monta a série diária contínua (calendário sem buracos, demanda real + suavizada) |
| `gerar_previsao` | Treina o Prophet e projeta a demanda para o horizonte escolhido |
| `avaliar_acuracia` | Executa o *backtest* e calcula MAE/MAPE/WAPE |
| `calcular_estoque_seguranca` | Calcula o estoque de segurança estatístico |
| `calcular_decisao_logistica` | Calcula ROP e EOQ |
| `main_app` | Orquestra a interface e apresenta os resultados |

O uso de `@st.cache_data` evita reprocessar os CSVs a cada interação, garantindo desempenho.

### 4.2 Funcionalidades e uso

Pela barra lateral, o gestor configura a simulação:

- **Departamento (Curva A)** a analisar;
- **Horizonte de previsão** (15 a 90 dias);
- **Lead time** do fornecedor;
- **Estoque de segurança**: estatístico (por nível de serviço) ou manual (valor fixo);
- **Custo de pedido** e **custo de manter estoque**.

Ao clicar em "Gerar Análise Logística", o aplicativo apresenta:

1. **Três cards de decisão** — demanda prevista para 30 dias, Ponto de Pedido (ROP) e Lote
   Econômico (EOQ);
2. **Interpretação gerencial em texto** — por exemplo: *"Assim que o estoque baixar para X unidades,
   emita uma ordem de reposição de Y unidades"*;
3. **Detalhamento do estoque de segurança** — com a conta aberta ($z$, $\sigma$, lead time);
4. **Confiabilidade da previsão (backtest)** — com MAE, MAPE e WAPE;
5. **Gráfico interativo da projeção** — série histórica, previsão e intervalo de incerteza.

### 4.3 Capturas de tela

> **[Inserir aqui as capturas de tela do aplicativo em execução]**
>
> - *Figura 1 — Painel gerencial (barra lateral) com os parâmetros de simulação.*
> - *Figura 2 — Cards de decisão (Demanda, ROP, EOQ) e interpretação gerencial.*
> - *Figura 3 — Seção de confiabilidade da previsão (MAE/MAPE/WAPE).*
> - *Figura 4 — Gráfico interativo da projeção de demanda (Plotly).*

### 4.4 Instalação e execução

```bash
# 1. Criar e ativar o ambiente virtual
python -m venv venv
.\venv\Scripts\Activate.ps1        # Windows (PowerShell)
# source venv/bin/activate         # macOS / Linux

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Executar o aplicativo
streamlit run "Previsão de compra/app.py"
```

A aplicação abre automaticamente em `http://localhost:8501`.

<div style="page-break-after: always;"></div>

## 5. Resultados e discussão

### 5.1 Resultados obtidos

A ferramenta foi exercitada com o dataset real (18.808 registros de vendas distribuídos ao longo de
714 dias de operação, após o tratamento). Os resultados confirmam a coerência da modelagem:

- **Seleção da Curva A** — o aplicativo identifica corretamente as categorias de maior giro recente,
  concentrando a análise onde está o maior impacto financeiro.
- **Cálculo do ROP** — a fórmula fecha de forma verificável. Para uma demanda média de 5 unid./dia,
  lead time de 7 dias e estoque de segurança de 50 unidades, o ROP resulta em
  $5 \times 7 + 50 = 85$ unidades, exatamente como esperado.
- **Estoque de segurança escalando com o nível de serviço** — para uma categoria típica, o SS cresce
  de forma coerente: cerca de **25 unidades a 80%**, **50 a 95%** e **71 a 99%**, evidenciando o
  trade-off entre nível de serviço e capital imobilizado.
- **EOQ** — produz lotes de compra economicamente equilibrados a partir dos custos informados.

### 5.2 Interpretação gerencial

O principal valor da ferramenta é traduzir números em **decisão**. Em vez de entregar apenas uma
previsão, o aplicativo diz ao gestor, em linguagem direta, *quando* disparar a compra (ROP) e
*quanto* comprar (EOQ), e ainda **quantifica a confiança** dessa recomendação por meio do backtest.
Isso responde à primeira pergunta de qualquer decisor — *"como sei que essa previsão acerta?"* — e
sustenta a adoção da ferramenta em uma operação real.

O estoque de segurança estatístico, em particular, conecta dois mundos que costumam ficar separados:
a **previsão** (o que esperamos vender) e a **proteção contra a incerteza** (o quanto a demanda
varia). Expor o nível de serviço como parâmetro coloca a decisão de risco nas mãos do gestor, de
forma transparente.

### 5.3 Limitações

- **Horizonte temporal do dado.** A base Olist termina em ~2018; "últimos 30 dias" é relativo ao
  histórico, não a tempo real. Em produção, a ferramenta consumiria dados atualizados.
- **Anualização do EOQ.** A demanda anual é estimada anualizando a média do horizonte
  ($\text{média} \times 365$), o que suaviza a sazonalidade capturada pelo Prophet — premissa a
  considerar na interpretação.
- **Proxy de unidades.** A contagem de itens não distingue com precisão múltiplas unidades idênticas
  no mesmo pedido.
- **Categorias isoladas.** O modelo trata cada categoria de forma independente, sem capturar efeitos
  cruzados (canibalização ou complementaridade entre categorias).
- **Dependência do Prophet em ambiente local.** As funções de previsão e backtest exigem o Prophet
  instalado; recomenda-se executar uma vez localmente antes da apresentação para validar o ambiente.

<div style="page-break-after: always;"></div>

## 6. Considerações finais

### 6.1 Síntese das contribuições

O trabalho entregou um **aplicativo funcional e demonstrável** que aplica métodos quantitativos da
disciplina a um problema logístico real de e-commerce. A solução integra, em um único fluxo:

- **Curva ABC** para focar nos itens de maior impacto;
- **Previsão de demanda** com Prophet, adequada a dados intermitentes;
- **Decisão de compra** com ROP, EOQ e estoque de segurança estatístico;
- **Validação do modelo** por backtest, com métricas de erro transparentes.

O diferencial em relação a uma simples previsão é a **integração previsão → decisão → validação**,
comunicada em linguagem gerencial. Isso transforma a ferramenta em um instrumento que poderia, de
fato, apoiar decisões de reposição em uma operação real.

### 6.2 Possíveis extensões

- **Estoque de segurança dinâmico** — usar a própria incerteza do Prophet (`yhat_upper`) como entrada
  alternativa para dimensionar o estoque de segurança.
- **Validação cruzada temporal** — múltiplos cortes de backtest (em vez de um único hold-out) para
  uma estimativa de erro mais estável.
- **Decisão multi-categoria** — incorporar restrições de capital ou de espaço compartilhadas entre
  categorias, aproximando-se de um problema de otimização de portfólio de estoque.
- **Integração com dados em tempo real** — conectar a ferramenta a um ERP/marketplace para alimentar
  a previsão com vendas atualizadas.

<div style="page-break-after: always;"></div>

## 7. Referências

CHOPRA, S.; MEINDL, P. **Gestão da Cadeia de Suprimentos: Estratégia, Planejamento e Operações.**
6. ed. São Paulo: Pearson, 2016.

BALLOU, R. H. **Gerenciamento da Cadeia de Suprimentos / Logística Empresarial.** 5. ed. Porto
Alegre: Bookman, 2006.

HARRIS, F. W. How Many Parts to Make at Once. *Factory, The Magazine of Management*, v. 10, n. 2,
p. 135-136, 1913.

TAYLOR, S. J.; LETHAM, B. Forecasting at Scale. *The American Statistician*, v. 72, n. 1, p. 37-45,
2018. (Modelo Prophet.) Disponível em: https://facebook.github.io/prophet/. Acesso em: 30 jun. 2026.

OLIST; SIONEK, A. **Brazilian E-Commerce Public Dataset by Olist.** Kaggle, 2018. Disponível em:
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce. Acesso em: 30 jun. 2026.

STREAMLIT INC. **Streamlit Documentation.** Disponível em: https://docs.streamlit.io/. Acesso em:
30 jun. 2026.

THE PANDAS DEVELOPMENT TEAM. **pandas documentation.** Disponível em: https://pandas.pydata.org/docs/.
Acesso em: 30 jun. 2026.
