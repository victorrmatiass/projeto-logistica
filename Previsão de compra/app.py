import os
import math
from datetime import datetime
import pandas as pd

try:
    import streamlit as st
except Exception:
    st = None

@st.cache_data() if st is not None else (lambda f: f)
def carregar_e_limpar_dados(dataset_path="dataset"):
    """Carrega os CSVs, junta com os produtos e agrupa as vendas por Categoria."""
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

def gerar_previsao(ts_df, categoria_selecionada, dias_futuros=30):
    """Gera previsão diária aplicando Média Móvel de 7 dias para suavizar a intermitência."""
    try:
        from prophet import Prophet
    except Exception:
        raise ImportError("Prophet não está instalado. Execute `pip install prophet`.")

    dfp = ts_df[ts_df["nome_exibicao"] == categoria_selecionada].copy()
    if dfp.empty:
        raise ValueError(f"Nenhum dado encontrado para {categoria_selecionada}")

    dfp = dfp.groupby("order_date")["sales"].sum().reset_index()
    dfp["ds"] = pd.to_datetime(dfp["order_date"])
    dfp["y"] = dfp["sales"].astype(float)
    dfp = dfp[["ds", "y"]].sort_values("ds")

    idx = pd.date_range(dfp["ds"].min(), dfp["ds"].max(), freq="D")
    all_dates = pd.DataFrame({"ds": idx})
    history = all_dates.merge(dfp, on="ds", how="left").fillna(0)

    # Guarda o dado real para o gráfico
    history["y_real"] = history["y"] 
    # Aplica suavização de 7 dias para treinar o modelo
    history["y"] = history["y"].rolling(window=7, min_periods=1).mean()

    model = Prophet(daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=True)
    model.fit(history)

    future = model.make_future_dataframe(periods=dias_futuros, freq="D")
    forecast = model.predict(future)

    # Corta valores negativos
    forecast['yhat'] = forecast['yhat'].clip(lower=0)
    forecast['yhat_lower'] = forecast['yhat_lower'].clip(lower=0)
    forecast['yhat_upper'] = forecast['yhat_upper'].clip(lower=0)

    # Devolve a realidade ao DataFrame para o Plotly desenhar corretamente
    history["y"] = history["y_real"]

    return history, forecast, model

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

# ==========================================
# INTERFACE DO APLICATIVO (STREAMLIT)
# ==========================================
def main_app():
    st.set_page_config(page_title="Sistema Logístico PME", layout="wide")
    
    st.title("📦 Sistema de Previsão de Demanda e Gestão de Estoques")
    st.markdown("*(Estudo de Caso: Gestão de Categorias em Seller Parceiro / Fulfillment)*")
    st.divider()

    with st.spinner("Processando histórico de dados logísticos..."):
        df = carregar_e_limpar_dados()
    
    top_categorias = get_top_categorias(df, 10)

    st.sidebar.header("⚙️ Painel Gerencial")
    st.sidebar.write("Ajuste as variáveis de simulação.")
    
    categoria_selecionada = st.sidebar.selectbox("Selecione o Departamento (Curva A):", top_categorias)
    dias_futuros = st.sidebar.slider("Horizonte de Previsão (Dias):", min_value=15, max_value=90, value=30, step=5)
    
    st.sidebar.markdown("---")
    lead_time = st.sidebar.number_input("Lead Time do Fornecedor (Dias):", min_value=1, value=7)
    estoque_seguranca = st.sidebar.number_input("Estoque de Segurança (Unid.):", min_value=0, value=20)
    custo_pedido = st.sidebar.number_input("Custo de Fazer Pedido (R$):", min_value=1.0, value=50.0)
    custo_estoque = st.sidebar.number_input("Custo de Manter Estoque (R$/ano):", min_value=0.1, value=2.0)

    if st.sidebar.button("Gerar Análise Logística", type="primary"):
        with st.spinner("Analisando série temporal e executando modelo preditivo (Prophet)..."):
            history, forecast, model = gerar_previsao(df, categoria_selecionada, dias_futuros)
            d_media, rop, eoq = calcular_decisao_logistica(
                forecast, dias_futuros, lead_time, custo_pedido, custo_estoque, estoque_seguranca
            )

        st.subheader(f"📊 Decisão de Compra Sugerida: Departamento de {categoria_selecionada}")
        
        col1, col2, col3 = st.columns(3)
        # Convertendo a demanda diária para mensal para ficar mais limpo visualmente
        col1.metric("Demanda Prevista (30 dias)", f"{int(math.ceil(d_media * 30))} unidades")
        col2.metric("Ponto de Pedido (ROP)", f"{int(math.ceil(rop))} unidades", "Avisar Fornecedor")
        col3.metric("Lote Econômico (EOQ)", f"{int(math.ceil(eoq))} unidades", "Quantidade a Comprar")
        
        st.info(f"**Interpretação Gerencial:** Assim que o estoque de **{categoria_selecionada}** baixar para **{int(math.ceil(rop))} unidades**, o gerente deve emitir uma ordem de reposição contendo exatamente **{int(math.ceil(eoq))} unidades**.")

        st.subheader("📈 Projeção de Demanda da Série Temporal")
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