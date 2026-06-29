# Projeto Logística

Projeto com dois módulos principais para análise e otimização logística:
- **Previsão de Compra**: Análise de série temporal de vendas por categoria
- **Roteirização**: Otimização de rotas de entrega usando algoritmos de roteamento

## 📋 Pré-requisitos

- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)
- Git (opcional)

## 🔧 Configuração Inicial

### 1. Criar um Ambiente Virtual

Um ambiente virtual isola as dependências do projeto, evitando conflitos com outros projetos Python.

#### No Windows (PowerShell ou CMD):

```bash
python -m venv venv
```

#### No macOS/Linux:

```bash
python3 -m venv venv
```

### 2. Ativar o Ambiente Virtual

#### No Windows (PowerShell):

```bash
.\venv\Scripts\Activate.ps1
```

#### No Windows (CMD):

```bash
venv\Scripts\activate.bat
```

#### No macOS/Linux:

```bash
source venv/bin/activate
```

Após ativar, você deve ver `(venv)` no início da linha do terminal.

### 3. Instalar Dependências

Com o ambiente virtual ativado, instale as dependências do projeto:

```bash
pip install -r requirements.txt
```

Se encontrar problemas com o arquivo requirements.txt, você pode instalar as dependências principais manualmente:

```bash
pip install streamlit pandas folium streamlit-folium ortools requests
```

## 🚀 Rodando os Projetos

Os dois projetos rodam como aplicações **Streamlit** separadas e precisam ser executados em terminais diferentes.

### Projeto 1: Previsão de Compra

Este projeto analisa padrões de vendas por categoria usando série temporal.

```bash
streamlit run "Previsão de compra/app.py"
```

A aplicação abrirá automaticamente em `http://localhost:8501`

### Projeto 2: Roteirização

Este projeto otimiza rotas de entrega em Recife usando algoritmos de roteamento.

```bash
streamlit run Roteirização/app.py
```

A aplicação abrirá automaticamente em `http://localhost:8501` (se for a primeira, ou em outra porta se a 8501 estiver em uso)

## 📦 Estrutura do Projeto

```
Projeto/
├── requirements.txt              # Dependências do projeto
├── README.md                      # Este arquivo
├── Previsão de compra/
│   ├── app.py                     # App Streamlit de previsão
│   └── dataset/
│       ├── olist_customers_dataset.csv
│       ├── olist_geolocation_dataset.csv
│       ├── olist_order_items_dataset.csv
│       ├── olist_order_payments_dataset.csv
│       ├── olist_order_reviews_dataset.csv
│       ├── olist_orders_dataset.csv
│       ├── olist_products_dataset.csv
│       ├── olist_sellers_dataset.csv
│       └── product_category_name_translation.csv
└── Roteirização/
    └── app.py                     # App Streamlit de roteirização
```

## 💡 Dicas Úteis

### Executar Ambos os Projetos Simultaneamente

Abra dois terminais separados:

**Terminal 1:**
```bash
.\venv\Scripts\Activate.ps1
streamlit run "Previsão de compra/app.py"
```

**Terminal 2:**
```bash
.\venv\Scripts\Activate.ps1
streamlit run Roteirização/app.py
```

### Desativar o Ambiente Virtual

Quando terminar de trabalhar, desative o ambiente virtual:

```bash
deactivate
```

### Atualizar Dependências

Se precisar instalar novas dependências:

```bash
pip install <nome_do_pacote>
pip freeze > requirements.txt
```

### Solucionar Problemas Comuns

**Erro: "módulo não encontrado"**
- Verifique se o ambiente virtual está ativado (deve aparecer `(venv)` no terminal)
- Reinstale as dependências: `pip install -r requirements.txt`

**Streamlit não abre**
- Verifique se a porta 8501 está disponível
- Tente especificar uma porta diferente: `streamlit run app.py --server.port 8502`

**Erro de arquivo não encontrado nos datasets**
- Certifique-se de estar executando os comandos da pasta raiz do projeto
- Verifique se os arquivos CSV existem em `Previsão de compra/dataset/`

## 📝 Notas Adicionais

- O projeto "Previsão de compra" utiliza dados da base OLIST e requer os arquivos CSV no diretório `dataset/`
- O projeto "Roteirização" utiliza dados de agências bancárias reais em Recife e pode usar a API OSRM ou distância Haversine como fallback
- Ambos os projetos usam **Streamlit** como framework para interface web interativa

## 📞 Suporte

Para mais informações sobre Streamlit, visite: https://streamlit.io/
Para OR-Tools: https://developers.google.com/optimization
