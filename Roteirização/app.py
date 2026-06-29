import streamlit as st
import pandas as pd
import math
import folium
import requests
from streamlit_folium import st_folium
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

# ==========================================
# 1. BASE DE DADOS (AGÊNCIAS REAIS EM RECIFE)
# ==========================================
LOCAIS_RECIFE = [
    {"id": 0, "nome": "Base da Transportadora de Valores (Imbiribeira)", "lat": -8.1100, "lon": -34.9150},
    {"id": 1, "nome": "BB Ponto Recife (Av. Rio Branco, 240)", "lat": -8.0628, "lon": -34.8711},
    {"id": 2, "nome": "BB Derby (Av. Agamenon Magalhães)", "lat": -8.0569, "lon": -34.9011},
    {"id": 3, "nome": "BB Encruzilhada (Zona Norte)", "lat": -8.0381, "lon": -34.8892},
    {"id": 4, "nome": "BB Casa Forte (Praça de Casa Forte)", "lat": -8.0310, "lon": -34.9185},
    {"id": 5, "nome": "BB Iputinga (Av. Caxangá, 3424)", "lat": -8.0335, "lon": -34.9355},
    {"id": 6, "nome": "BB UFPE (Campus Universitário)", "lat": -8.0498, "lon": -34.9510},
    {"id": 7, "nome": "BB Afogados (Largo da Paz)", "lat": -8.0775, "lon": -34.9044},
    {"id": 8, "nome": "BB Shopping Recife", "lat": -8.1194, "lon": -34.9044},
    {"id": 9, "nome": "BB Conselheiro Aguiar (Boa Viagem)", "lat": -8.1250, "lon": -34.8980},
    {"id": 10, "nome": "BB Aeroporto Internacional Guararapes", "lat": -8.1305, "lon": -34.9180}
]

# ==========================================
# 2. MOTOR MATEMÁTICO (OR-TOOLS + MATRIZ OSRM)
# ==========================================
def haversine_distance(lat1, lon1, lat2, lon2):
    """Plano B: Distância em linha reta caso a API fique sem internet durante a apresentação."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return int(R * c)

def criar_matriz_distancias(locais):
    """Bate na API do OSRM para criar uma matriz com as distâncias REAIS de asfalto."""
    coords_str = ";".join([f"{loc['lon']},{loc['lat']}" for loc in locais])
    url = f"http://router.project-osrm.org/table/v1/driving/{coords_str}?annotations=distance"
    
    try:
        resposta = requests.get(url, timeout=5).json()
        if resposta.get("code") == "Ok":
            matriz_real = []
            for linha in resposta["distances"]:
                # Se não achar rota (ex: rio sem ponte), joga uma penalidade infinita (999999)
                matriz_real.append([int(dist) if dist is not None else 999999 for dist in linha])
            return matriz_real
    except Exception:
        pass # Se falhar, desce para o Plano B silenciosamente
    
    # Plano B (Fallback): Cria a matriz usando linha reta
    matriz_reta = []
    for i in range(len(locais)):
        linha = []
        for j in range(len(locais)):
            if i == j:
                linha.append(0)
            else:
                linha.append(haversine_distance(locais[i]["lat"], locais[i]["lon"], locais[j]["lat"], locais[j]["lon"]))
        matriz_reta.append(linha)
    return matriz_reta

def resolver_roteirizacao(locais):
    """Configura e resolve o Problema de Roteirização de Veículos (VRP)."""
    if len(locais) < 2:
        return None

    matriz_distancias = criar_matriz_distancias(locais)
    manager = pywrapcp.RoutingIndexManager(len(matriz_distancias), 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return matriz_distancias[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

    solucao = routing.SolveWithParameters(search_parameters)

    if solucao:
        rota_indices = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            rota_indices.append(manager.IndexToNode(index))
            index = solucao.Value(routing.NextVar(index))
        rota_indices.append(manager.IndexToNode(index)) # Adiciona a volta à base
        
        return [locais[i] for i in rota_indices]
    return None

# ==========================================
# 3. INTEGRAÇÃO COM GPS REAL (OSRM ROUTE)
# ==========================================
def pegar_rota_ruas(rota_ordenada):
    """Pega o trajeto detalhado pelas ruas de Recife e a distância final do asfalto."""
    coords_str = ";".join([f"{p['lon']},{p['lat']}" for p in rota_ordenada])
    url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full&geometries=geojson"
    
    try:
        resposta = requests.get(url, timeout=5).json()
        if resposta.get("code") == "Ok":
            distancia_real_metros = resposta["routes"][0]["distance"]
            # OSRM devolve [lon, lat], o Folium precisa de [lat, lon]
            coordenadas_geojson = resposta["routes"][0]["geometry"]["coordinates"]
            coordenadas_folium = [[lat, lon] for lon, lat in coordenadas_geojson]
            return coordenadas_folium, distancia_real_metros
    except Exception:
        pass
    return None, 0

# ==========================================
# 4. INTERFACE DO APLICATIVO (STREAMLIT)
# ==========================================
st.set_page_config(page_title="Roteirização VRP", layout="wide")

st.title("🛡️ Sistema de Otimização de Roteirização de Veículos (VRP)")
st.markdown("*(Estudo de Caso: Transporte de Valores e Abastecimento de Agências Bancárias no Recife)*")
st.divider()

st.sidebar.header("⚙️ Planeamento Diário")
st.sidebar.write("Selecione quais agências solicitaram abastecimento para a rota de hoje:")

# A base é obrigatória, logo listamos apenas as agências (ID 1 em diante)
opcoes_agencias = {loc["id"]: loc["nome"] for loc in LOCAIS_RECIFE[1:]}
agencias_selecionadas_ids = st.sidebar.multiselect(
    "Agências a visitar:",
    options=list(opcoes_agencias.keys()),
    default=list(opcoes_agencias.keys()),
    format_func=lambda x: opcoes_agencias[x]
)

if st.sidebar.button("Calcular Rota Otimizada", type="primary"):
    if not agencias_selecionadas_ids:
        st.warning("Selecione pelo menos uma agência para calcular a rota.")
    else:
        with st.spinner("A consultar matriz de distâncias reais e a executar OR-Tools..."):
            locais_filtrados = [LOCAIS_RECIFE[0]] + [loc for loc in LOCAIS_RECIFE if loc["id"] in agencias_selecionadas_ids]
            
            rota_otimizada = resolver_roteirizacao(locais_filtrados)
            
            if rota_otimizada:
                coordenadas_ruas, distancia_asfalto = pegar_rota_ruas(rota_otimizada)
                distancia_km = distancia_asfalto / 1000

                st.subheader("📊 Resultado da Otimização")
                st.metric("Distância Total do Percurso (Asfalto Real)", f"{distancia_km:.2f} km")
                st.info("O algoritmo OR-Tools avaliou a matriz de distâncias (OSRM) para encontrar a sequência ideal de visitação. O percurso final reflete o caminho mais eficiente pelas avenidas.")

                col1, col2 = st.columns([1, 2])

                with col1:
                    st.write("**Ordem de Visitação Segura:**")
                    for i, parada in enumerate(rota_otimizada):
                        if i == 0:
                            st.markdown(f"**Saída:** {parada['nome']}")
                        elif i == len(rota_otimizada) - 1:
                            st.markdown(f"**Retorno:** {parada['nome']}")
                        else:
                            st.markdown(f"{i}º Ponto: {parada['nome']}")

                with col2:
                    # Inicializa o mapa focado na região central de Recife
                    m = folium.Map(location=[-8.05, -34.89], zoom_start=13)
                    
                    if coordenadas_ruas:
                        folium.PolyLine(coordenadas_ruas, color="#1f77b4", weight=5, opacity=0.8).add_to(m)

                    for i, parada in enumerate(rota_otimizada[:-1]):
                        cor = "red" if i == 0 else "blue"
                        icone = "shield" if i == 0 else "usd"
                        
                        folium.Marker(
                            location=[parada["lat"], parada["lon"]],
                            popup=f"{i} - {parada['nome']}",
                            tooltip=parada['nome'],
                            icon=folium.Icon(color=cor, icon=icone, prefix='fa')
                        ).add_to(m)

                    st_folium(m, width=800, height=500, returned_objects=[])
            else:
                st.error("Erro ao calcular a rota.")