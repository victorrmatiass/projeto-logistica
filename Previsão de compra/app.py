import os
import math
from datetime import datetime
import pandas as pd

try:
    import streamlit as st
except Exception:
    st = None

# Pasta onde este app.py está, para achar o dataset independente de onde o Streamlit é iniciado
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@st.cache_data() if st is not None else (lambda f: f)
def carregar_e_limpar_dados(dataset_path=None):
    """Carrega os CSVs, junta com os produtos e agrupa as vendas por Categoria."""
    if dataset_path is None:
        dataset_path = os.path.join(BASE_DIR, "dataset")

    orders_fp = os.path.join(dataset_path, "olist_orders_dataset.csv")
    items_fp = os.path.join(dataset_path, "olist_order_items_dataset.csv")
    products_fp = os.path.join(dataset_path, "olist_products_dataset.csv")

    if not (os.path.exists(orders_fp) and os.path.exists(items_fp) and os.path.exists(products_fp)):
        raise FileNotFoundError(
            f"Arquivos não encontrados em '{dataset_path}'. Verifique se os 3 CSVs estão lá."
        )

    orders = pd.read_csv(orders_fp, parse_dates=["order_purchase_timestamp"], low_memory=False)
    items = pd.read_csv(items_fp, low_memory=False)
    products = pd.read_csv(products_fp, low_memory=False)

    if "order_status" in orders.columns:
        delivered_mask = orders["order_status"].str.lower() == "delivered"
        if delivered_mask.any():
            orders = orders[delivered_mask]

    # Cruzamento de tabelas
    merged = items.merge(orders[["order_id", "order_purchase_timestamp"]], on="order_id", how="inner")
    merged = merged.merge(products[["product_id", "product_category_name"]], on="product_id", how="left")
    
    # Tratamento de texto
    merged["product_category_name"] = merged["product_category_name"].fillna("categoria_desconhecida")
    merged["nome_exibicao"] = merged["product_category_name"].str.replace("_", " ").str.title()

    merged["order_date"] = pd.to_datetime(merged["order_purchase_timestamp"]).dt.date
    
    # Agrupando APENAS pela categoria e data
    ts = merged.groupby(["nome_exibicao", "order_date"]).size().reset_index(name="sales")
    ts["sales"] = ts["sales"].astype(int)

    return ts

def get_top_categorias(ts_df, top_n=10, dias_analise=30):
    """Retorna as categorias mais vendidas focando apenas nos últimos 30 dias de operação."""
    ultima_data = pd.to_datetime(ts_df["order_date"]).max()
    data_corte = (ultima_data - pd.Timedelta(days=dias_analise)).date()

    df_recente = ts_df[ts_df["order_date"] >= data_corte]
    totals = df_recente.groupby("nome_exibicao")["sales"].sum().reset_index()
    top = totals.sort_values("sales", ascending=False).head(top_n)
    
    return top["nome_exibicao"].tolist()

def _preparar_serie_diaria(ts_df, categoria_selecionada):
    """Monta a série temporal diária contínua (sem buracos de calendário) de uma
    categoria. Retorna a demanda real (y_real) e a versão suavizada por Média Móvel
    de 7 dias (y), usada para treinar o modelo e reduzir a intermitência."""
    dfp = ts_df[ts_df["nome_exibicao"] == categoria_selecionada].copy()
    if dfp.empty:
        raise ValueError(f"Nenhum dado encontrado para {categoria_selecionada}")

    dfp = dfp.groupby("order_date")["sales"].sum().reset_index()
    dfp["ds"] = pd.to_datetime(dfp["order_date"])
    dfp["y"] = dfp["sales"].astype(float)
    dfp = dfp[["ds", "y"]].sort_values("ds")

    # Preenche os dias sem nenhuma venda com 0 (calendário contínuo é exigido pelo Prophet)
    idx = pd.date_range(dfp["ds"].min(), dfp["ds"].max(), freq="D")
    all_dates = pd.DataFrame({"ds": idx})
    history = all_dates.merge(dfp, on="ds", how="left").fillna(0)

    history["y_real"] = history["y"]                              # demanda real (para gráfico/avaliação)
    history["y"] = history["y"].rolling(window=7, min_periods=1).mean()  # suavizada (para treino)
    return history

def gerar_previsao(ts_df, categoria_selecionada, dias_futuros=30):
    """Treina o Prophet na série suavizada e projeta a demanda para o horizonte futuro."""
    try:
        from prophet import Prophet
    except Exception:
        raise ImportError("Prophet não está instalado. Execute `pip install prophet`.")

    history = _preparar_serie_diaria(ts_df, categoria_selecionada)

    model = Prophet(daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=True)
    model.fit(history)

    future = model.make_future_dataframe(periods=dias_futuros, freq="D")
    forecast = model.predict(future)

    # Corta valores negativos (demanda não pode ser menor que zero)
    for col in ("yhat", "yhat_lower", "yhat_upper"):
        forecast[col] = forecast[col].clip(lower=0)

    # Devolve a realidade ao DataFrame para o Plotly desenhar corretamente
    history["y"] = history["y_real"]

    return history, forecast, model

def avaliar_acuracia(ts_df, categoria_selecionada, dias_teste=30):
    """Backtest (validação histórica): esconde os últimos `dias_teste` dias, treina o
    Prophet somente com o passado e compara a previsão contra a demanda real escondida.
    Retorna MAE, MAPE e WAPE — a evidência de quão confiável é o modelo."""
    try:
        from prophet import Prophet
    except Exception:
        raise ImportError("Prophet não está instalado. Execute `pip install prophet`.")

    history = _preparar_serie_diaria(ts_df, categoria_selecionada)

    # Sem histórico suficiente, um teste de 30 dias não seria confiável
    if len(history) <= dias_teste + 30:
        return None

    treino = history.iloc[:-dias_teste]
    teste = history.iloc[-dias_teste:]

    model = Prophet(daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=True)
    model.fit(treino[["ds", "y"]])

    prev = model.predict(teste[["ds"]])
    y_real = teste["y_real"].values
    y_prev = prev["yhat"].clip(lower=0).values

    erro_abs = abs(y_real - y_prev)
    mae = float(erro_abs.mean())

    # MAPE apenas nos dias com venda real (evita divisão por zero em dias parados)
    mask = y_real > 0
    mape = float((erro_abs[mask] / y_real[mask]).mean() * 100) if mask.any() else None

    # WAPE: erro absoluto sobre o volume total — robusto a dias zerados, mais honesto aqui
    soma = y_real.sum()
    wape = float(erro_abs.sum() / soma * 100) if soma > 0 else None

    # ----- Baseline ingênua: prever TODO dia como a média histórica de vendas -----
    # É o "fazer o simples"; o modelo só vale a pena se errar menos que isso.
    media_historica = float(treino["y_real"].mean())
    erro_base = abs(y_real - media_historica)
    base_mae = float(erro_base.mean())
    base_wape = float(erro_base.sum() / soma * 100) if soma > 0 else None

    # Quanto o modelo reduz o WAPE em relação à baseline (positivo = modelo melhor)
    if wape is not None and base_wape and base_wape > 0:
        melhora_wape = (base_wape - wape) / base_wape * 100
    else:
        melhora_wape = None

    return {
        "mae": mae, "mape": mape, "wape": wape,
        "base_mae": base_mae, "base_wape": base_wape, "melhora_wape": melhora_wape,
        "dias_teste": dias_teste,
    }

def calcular_decisao_logistica(forecast_df, dias_futuros, lead_time, custo_pedido, custo_estoque, estoque_seguranca):
    """Aplica as equações de Ponto de Pedido (ROP) e Lote Econômico (EOQ)."""
    futuro = forecast_df.tail(dias_futuros)
    
    demanda_media_diaria = max(0, futuro['yhat'].mean())
    demanda_anual = demanda_media_diaria * 365

    rop = (demanda_media_diaria * lead_time) + estoque_seguranca

    if custo_estoque > 0 and demanda_anual > 0:
        eoq = math.sqrt((2 * demanda_anual * custo_pedido) / custo_estoque)
    else:
        eoq = 0

    return demanda_media_diaria, rop, eoq

# Z da Normal padrão por nível de serviço (tabela fixa para não depender do scipy)
Z_NIVEL_SERVICO = {80: 0.84, 85: 1.04, 90: 1.28, 95: 1.65, 97: 1.88, 99: 2.33}

def calcular_estoque_seguranca(history, lead_time, nivel_servico):
    """Estoque de Segurança estatístico: SS = z * desvio-padrão da demanda diária * raiz(lead time).
    Conecta a variabilidade real da demanda ao nível de serviço desejado, em vez de chutar
    um valor fixo. Retorna o SS e os componentes (z e sigma) para fins de interpretação."""
    z = Z_NIVEL_SERVICO.get(nivel_servico, 1.65)
    sigma_diario = float(history["y_real"].std())
    ss = z * sigma_diario * math.sqrt(lead_time)
    return ss, z, sigma_diario

# ==========================================
# INTERFACE DO APLICATIVO (STREAMLIT)
# ==========================================
def main_app():
    st.set_page_config(page_title="Sistema Logístico PME", layout="wide")
    
    st.title("Sistema de Previsão de Demanda e Gestão de Estoques")
    st.markdown("*(Estudo de Caso: Gestão de Categorias em Seller Parceiro / Fulfillment)*")
    st.divider()

    with st.spinner("Processando histórico de dados logísticos..."):
        df = carregar_e_limpar_dados()
    
    top_categorias = get_top_categorias(df, 10)

    st.sidebar.header("Painel Gerencial")
    st.sidebar.write("Ajuste as variáveis de simulação.")
    
    categoria_selecionada = st.sidebar.selectbox("Selecione o Departamento (Curva A):", top_categorias)
    dias_futuros = st.sidebar.slider("Horizonte de Previsão (Dias):", min_value=15, max_value=90, value=30, step=5)
    
    st.sidebar.markdown("---")
    lead_time = st.sidebar.number_input("Lead Time do Fornecedor (Dias):", min_value=1, value=7)

    metodo_ss = st.sidebar.radio(
        "Estoque de Segurança:",
        ["Estatístico (nível de serviço)", "Manual (valor fixo)"],
        help="O método estatístico deriva o estoque da variabilidade real da demanda: SS = z · σ · √lead time."
    )
    if metodo_ss.startswith("Estatístico"):
        nivel_servico = st.sidebar.select_slider(
            "Nível de Serviço Desejado (%):",
            options=[80, 85, 90, 95, 97, 99], value=95
        )
        estoque_seguranca_manual = None
    else:
        nivel_servico = None
        estoque_seguranca_manual = st.sidebar.number_input("Estoque de Segurança (Unid.):", min_value=0, value=20)

    custo_pedido = st.sidebar.number_input("Custo de Fazer Pedido (R$):", min_value=1.0, value=50.0)
    custo_estoque = st.sidebar.number_input("Custo de Manter Estoque (R$/ano):", min_value=0.1, value=2.0)

    if st.sidebar.button("Gerar Análise Logística", type="primary"):
        with st.spinner("Analisando série temporal e executando modelo preditivo (Prophet)..."):
            history, forecast, model = gerar_previsao(df, categoria_selecionada, dias_futuros)

            # Define o estoque de segurança conforme o método escolhido
            if metodo_ss.startswith("Estatístico"):
                estoque_seguranca, z_usado, sigma_diario = calcular_estoque_seguranca(
                    history, lead_time, nivel_servico
                )
            else:
                estoque_seguranca, z_usado, sigma_diario = estoque_seguranca_manual, None, None

            d_media, rop, eoq = calcular_decisao_logistica(
                forecast, dias_futuros, lead_time, custo_pedido, custo_estoque, estoque_seguranca
            )

            # Validação histórica do modelo (backtest)
            metricas = avaliar_acuracia(df, categoria_selecionada)

        st.subheader(f"Decisão de Compra Sugerida: Departamento de {categoria_selecionada}")

        col1, col2, col3 = st.columns(3)
        # Convertendo a demanda diária para mensal para ficar mais limpo visualmente
        col1.metric("Demanda Prevista (30 dias)", f"{int(math.ceil(d_media * 30))} unidades")
        col2.metric("Ponto de Pedido (ROP)", f"{int(math.ceil(rop))} unidades", "Avisar Fornecedor")
        col3.metric("Lote Econômico (EOQ)", f"{int(math.ceil(eoq))} unidades", "Quantidade a Comprar")

        st.info(f"**Interpretação Gerencial:** Assim que o estoque de **{categoria_selecionada}** baixar para **{int(math.ceil(rop))} unidades**, o gerente deve emitir uma ordem de reposição contendo exatamente **{int(math.ceil(eoq))} unidades**.")

        # ----- Estoque de Segurança (transparência do cálculo) -----
        if z_usado is not None:
            st.caption(
                f"**Estoque de Segurança (estatístico):** {int(math.ceil(estoque_seguranca))} unidades  "
                f"= z ({z_usado:.2f}, nível {nivel_servico}%) × σ da demanda diária ({sigma_diario:.2f}) "
                f"× √lead time ({lead_time}d). Já está embutido no ROP acima."
            )
        else:
            st.caption(
                f"**Estoque de Segurança (manual):** {int(math.ceil(estoque_seguranca))} unidades, "
                "informado pelo gestor e embutido no ROP."
            )

        # ----- Confiabilidade do modelo (backtest) -----
        st.subheader("Confiabilidade da Previsão (Backtest)")
        if metricas is None:
            st.warning(
                "Histórico curto demais para um backtest confiável desta categoria "
                "(são necessários mais de ~60 dias de dados)."
            )
        else:
            wape_txt = f"{metricas['wape']:.1f}%" if metricas["wape"] is not None else "—"
            base_wape_txt = f"{metricas['base_wape']:.1f}%" if metricas["base_wape"] is not None else "—"

            m1, m2 = st.columns(2)
            m1.metric("Erro Médio Absoluto (MAE)", f"{metricas['mae']:.1f} unid./dia")
            m2.metric("Erro Percentual (WAPE)", wape_txt)

            # Comparação com a baseline ingênua (prever sempre a média histórica)
            melhora = metricas["melhora_wape"]
            if melhora is not None and melhora > 0:
                st.success(
                    f"✅ O modelo erra **{wape_txt}** (WAPE), contra **{base_wape_txt}** de uma previsão "
                    f"**ingênua** (chutar sempre a média histórica) — uma **melhora de {melhora:.0f}%**. "
                    f"O modelo agrega valor à decisão de compra."
                )
            elif melhora is not None:
                st.warning(
                    f"⚠️ O modelo erra **{wape_txt}** (WAPE), contra **{base_wape_txt}** da previsão ingênua "
                    f"(chutar sempre a média histórica). Nesta categoria o modelo **não supera** o método simples "
                    f"— sinal de demanda muito errática/sazonal. Aqui vale apoiar a decisão no estoque de "
                    f"segurança e num nível de serviço mais alto."
                )

            mape_txt = f"{metricas['mape']:.0f}%" if metricas["mape"] is not None else "—"
            st.caption(
                f"Validação escondendo os últimos {metricas['dias_teste']} dias e treinando só com o passado. "
                f"**WAPE** (métrica principal) = erro absoluto sobre o volume total, robusto a dias sem venda. "
                f"**MAE** = unidades/dia erradas, em média. "
                f"O **MAPE ({mape_txt})** aparece só por convenção: em demanda diária intermitente ele **infla "
                f"artificialmente** (dias de venda baixa distorcem a média), por isso não é a referência aqui. "
                f"Quanto menor, mais confiável a decisão de compra."
            )

        st.subheader("Projeção de Demanda da Série Temporal")
        from prophet.plot import plot_plotly
        
        fig = plot_plotly(model, forecast, xlabel="Data da Venda", ylabel="Unidades Vendidas")
        
        # Transforma os marcadores esparsos em uma linha contínua
        fig.data[0].mode = 'lines'
        
        fig.update_layout(
            margin=dict(l=0, r=0, t=30, b=0),
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    if st is None:
        print("Streamlit não importado. Execute o script usando: streamlit run app.py")
    else:
        main_app()