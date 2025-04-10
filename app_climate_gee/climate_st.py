import geemap               # Ferramentas para integração com o Google Earth Engine e mapas interativos
import ee                   # Biblioteca oficial do Google Earth Engine para Python (processamento de dados geoespaciais)
import geemap.foliumap as geemap  # Versão do geemap baseada no folium, usada para renderizar mapas no Streamlit

from datetime import datetime       # Utilizado para manipular datas (seleção do período de análise)
import streamlit as st              # Framework principal do app (interface web interativa)
from streamlit_folium import st_folium  # Permite integrar mapas Folium interativos ao Streamlit

import folium                # Biblioteca de mapas interativos baseada em Leaflet.js (usada para desenho da ROI)
import plotly.express as px  # Gráficos simples e rápidos)
import plotly.graph_objects as go  # Usado para gráficos avançados (ex: série temporal, indicadores)

import altair as alt         # Biblioteca de visualização declarativa (usada para o gráfico de calor e séries temporais do PDSI)
import pandas as pd          # Manipulação de tabelas e dataframes
import time                  # Pausa no processamento (ex: spinner de carregamento)
import geopandas as gpd      # ⚠️ Não está sendo utilizada diretamente (mas pode estar usada dentro de `convert_to_geodf`)
from utils_geo import convert_to_geodf  # Função personalizada que converte o upload em GeoDataFrame
import json                  # Manipulação de GeoJSONs e estruturação dos dados para download/sessão
import tempfile
from google.oauth2 import service_account
from ee import oauth
 

# ====================================================
# CONFIGURAÇÃO INICIAL DA PÁGINA
# ====================================================
st.set_page_config(layout="wide")
# Inicializa um mapa apenas para garantir autenticação do Earth Engine
auth_map = geemap.Map()
st.title('Análise Variáveis Climáticas (P - ET)')
st.markdown("""
O APP permite que o usuário visualize uma série temporal mensal de Precipitação, 
Evapotranspiração, Balanço Hídrico (P-ET) e Índice de Seca Palmer.   
Para construção deste APP foram utilizadas imagens CHIRPS, MOD16 e TERRACLIMATE.
""")

# Spinner de carregamento inicial
st.subheader('Processamento de dados', divider='blue')
with st.spinner('Aguarde o processamento dos dados...'):
    time.sleep(2)
st.success('Informações Processadas!')

# ====================================================
# BARRA LATERAL (SIDEBAR) - Upload e desenho da ROI
# ====================================================
st.sidebar.image("asset/ambgeo.png")

# Upload de arquivo com geometria
uploaded_file = st.sidebar.file_uploader(
    "Faça o upload da sua área de estudo", 
    type=["geojson", "kml", "kmz", "gpkg", "zip"]
)

# Alternativa: desenho direto da ROI
st.sidebar.markdown("### Ou desenhe sua área no mapa abaixo ⬇️")

# ====================================================
# DEFINIÇÃO DA REGIÃO DE INTERESSE (ROI)
# ====================================================
roi = None  # Variável global para armazenar a ROI

# CASO 1: Nenhum upload e nenhuma ROI na sessão → mapa para desenho
if uploaded_file is None and "roi_uploaded" not in st.session_state:
    st.subheader("Desenhe sua área de interesse")
  

    # Cria mapa base com ferramenta de desenho
    folium_map = folium.Map(location=[-14, -54], zoom_start=5)
    draw = folium.plugins.Draw(export=True)
    draw.add_to(folium_map)

    # Captura do desenho feito pelo usuário
    draw_result = st_folium(folium_map, height=600, width=1000)

    # Se houver geometria desenhada, define como ROI
    if draw_result and draw_result.get("all_drawings"):
        feature = draw_result["all_drawings"][0]
        geojson_geom = feature["geometry"]
        roi = ee.Geometry(geojson_geom)

        # Salva no estado da sessão para reutilização futura
        st.session_state["roi_uploaded"] = True
        st.session_state["roi_geojson"] = feature

        # Feedback e botão de download da ROI
        st.sidebar.success("✅ ROI desenhada definida.")
        st.sidebar.download_button(
            "📥 Baixar ROI", 
            data=json.dumps(feature), 
            file_name="roi.geojson", 
            mime="application/geo+json"
        )
        st.rerun()

# CASO 2: Upload de arquivo vetorial → define a ROI
elif uploaded_file is not None:
    try:
        # Converte arquivo carregado em GeoDataFrame e depois para FeatureCollection do EE
        gdf = convert_to_geodf(uploaded_file)
        shp_json = gdf.to_json()
        f_json = json.loads(shp_json)['features']
        roi = ee.FeatureCollection(f_json)

        # Salva a geometria no estado da sessão
        st.session_state["roi_uploaded"] = True
        st.session_state["roi_geojson"] = {
            "type": "Feature",
            "geometry": f_json[0]['geometry']
        }

        st.sidebar.success("✅ Arquivo carregado com sucesso!")
    except Exception as e:
        st.sidebar.error(f"Erro ao carregar o arquivo: {e}")

# CASO 3: ROI já definida anteriormente → carrega da sessão
elif "roi_uploaded" in st.session_state:
    geojson_geom = st.session_state["roi_geojson"]["geometry"]
    roi = ee.Geometry(geojson_geom)

# ====================================================
# VISUALIZAÇÃO DA ROI NO MAPA (GEEMAP)
# ====================================================
if roi is not None and not st.session_state.get("analysis_done", False):
    st.subheader("Visualização da Região de Interesse")

    # Cria o mapa GEEMAP com a ROI
    m = geemap.Map(height=600)
    m.centerObject(roi, 8)
    m.setOptions("HYBRID")
    m.addLayer(roi, {}, "Região de Interesse")

    # O mapa ainda não está sendo renderizado neste trecho
    # Para exibir: descomente a linha abaixo
    # m.to_streamlit()

    
######################## COLEÇÃO DE IMAGENS ########################

# Sidebar - seleção de datas e botão de análise
start_date = st.sidebar.date_input("Selecione a data inicial", datetime(2024, 1, 1))
end_date = st.sidebar.date_input("Selecione a data final", datetime.now())
run_analysis = st.sidebar.button("🚀 Executar Análise")

# Executa o processamento somente se ROI foi definida e botão clicado
if roi is not None and run_analysis:

    ## Abrindo nossos dados
    chirps = ee.ImageCollection("UCSB-CHG/CHIRPS/PENTAD").select('precipitation')

    # Definindo a função de escala
    def scale_mod16(image):
        return image.multiply(0.1).copyProperties(image, image.propertyNames())

    mod16 = ee.ImageCollection("MODIS/061/MOD16A2GF").map(scale_mod16 ).select('ET')

    ## Definição de período
    year_start = start_date.year
    year_end = end_date.year

    # Parâmetros para padronização temporal
    startDate = ee.Date.fromYMD(year_start, 1, 1)
    endDate = ee.Date.fromYMD(year_end, 1, 1)  # Avança o ano inicial mais x

    # Filtrar a coleção a partir do período definido
    yearFiltered = chirps.filter(ee.Filter.date(startDate, endDate)).filterBounds(roi)
    # print('Numero de imagens',yearFiltered.size().getInfo())

    # Lista de meses e anos
    months = ee.List.sequence(1, 12)
    years = ee.List.sequence(year_start, (year_end - 1))

    # Função para criar imagens mensais
    def createYearly(year):

        def createMonthlyImage(month):
            return yearFiltered \
                .filter(ee.Filter.calendarRange(year, year, 'year')) \
                .filter(ee.Filter.calendarRange(month, month, 'month')) \
                .sum() \
                .clip(roi) \
                .set('year', year) \
                .set('month', month) \
                .set('data', ee.Date.fromYMD(year, month, 1).format()) \
                .set('system:time_start', ee.Date.fromYMD(year, month, 1))

        return months.map(createMonthlyImage)

    # Aplicar função mês/ano nas coleções
    chirps_monthlyImages = ee.ImageCollection.fromImages(years.map(createYearly).flatten())
    yearFiltered = mod16.filter(ee.Filter.date(startDate, endDate)).filterBounds(roi)
    mod16_monthlyImages = ee.ImageCollection.fromImages(years.map(createYearly).flatten())

    # Verificar número de bandas
    def addNumBands(image):
        num_bands = image.bandNames().size()
        return image.set('nbands', num_bands)

    # Aplica a função e filtra imagens com bandas válidas
    mod16_monthlyImages = mod16_monthlyImages.map(addNumBands).filter(ee.Filter.gt('nbands', 0))
    chirps_monthlyImages = chirps_monthlyImages.map(addNumBands).filter(ee.Filter.gt('nbands', 0))

    ## Cálculo do Balanço Hídrico
    def calculateWaterBalance(image):
        P = image.select('precipitation')
        ET = image.select('ET')
        waterBalance = P.subtract(ET)
        return image.addBands([waterBalance.rename('water_balance')])

    # Adicionar bandas de precipitação e evapotranspiração às imagens CHIRPS
    def addETBands(image):
        ET_image = mod16_monthlyImages \
            .filter(ee.Filter.eq('year', image.get('year'))) \
            .filter(ee.Filter.eq('month', image.get('month'))) \
            .first()
        return image.addBands([ET_image.rename('ET')])

    # Aplica as funções
    waterBalanceWithBands = chirps_monthlyImages.map(addETBands)
    waterBalanceResult = waterBalanceWithBands.map(calculateWaterBalance)

    ## Função para extrair estatísticas das imagens
    def stats(image):
        reduce = image.reduceRegions(**{
            'collection': roi,
            'reducer': ee.Reducer.mean(),
            'scale': 5000
        })

        reduce = reduce \
            .map(lambda f: f.set({'data': image.get('data')})) \
            .map(lambda f: f.set({'year': image.get('year')})) \
            .map(lambda f: f.set({'month': image.get('month')}))

        return reduce.copyProperties(image, image.propertyNames())

    # Converter para df
    col_bands = waterBalanceResult  # .select(bands)

    # Aplicar estatísticas
    stats_reduce = col_bands.map(stats) \
        .flatten() \
        .sort('data', True)
   

    df = geemap.ee_to_df(stats_reduce)
    

    ## Criando o gráfico com Plotly
    fig = go.Figure()

    # Barras para balanço hídrico (eixo secundário)
    fig.add_trace(go.Bar(
        x=df['data'], 
        y=df['water_balance'], 
        name='Wb', 
        yaxis='y2', 
        marker_color='orange'
    ))

    # Linhas para ET e Precipitação
    fig.add_trace(go.Scatter(
        x=df['data'], 
        y=df['ET'], 
        mode='lines', 
        name='ET', 
        line=dict(color='green')
    ))
    fig.add_trace(go.Scatter(
        x=df['data'], 
        y=df['precipitation'], 
        mode='lines', 
        name='P', 
        line=dict(color='blue')
    ))

    # Layout do gráfico
    fig.update_layout(
        title='Balanço Hídrico (P-ET)',
        yaxis=dict(title='ET & P mm/m'),
        yaxis2=dict(title='Wb (mm/m)', overlaying='y', side='right')
    )


    ######################## PDSI - Palmer Drought Severity Index ###############################

    # Função para aplicar escala e definir data nas imagens PDSI
    def scale_pdsi(image):
        return image.multiply(0.01).clip(roi) \
                    .set('data', image.date().format('YYYY-MM-dd')) \
                    .copyProperties(image, image.propertyNames())

    # Coleção PDSI (TERRACLIMATE)
    pdsi = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE") \
                .select('pdsi') \
                .map(scale_pdsi) \
                .filter(ee.Filter.date(startDate, endDate)) \
                .filterBounds(roi)

    # Redução espacial - cálculo de média por ROI
    def stats_pdsi(image):
        reduce = image.reduceRegions(**{
            'collection': roi,
            'reducer': ee.Reducer.mean(),
            'scale': 5000
        })

        reduce = reduce.map(lambda f: f.set({'data': image.get('data')}))
        return reduce.copyProperties(image, image.propertyNames())

    # Reduz, ordena e renomeia colunas
    stats_reduce = pdsi.map(stats_pdsi) \
                    .flatten() \
                    .sort('data', True) \
                    .select(['data', 'mean'], ['data', 'pdsi'])

    # Converte os dados para DataFrame
    df_pdsi = geemap.ee_to_df(stats_reduce)

    # Conversão de data para datetime
    df_pdsi['data'] = pd.to_datetime(df_pdsi['data'])

    # Extração de mês e ano
    df_pdsi['mes'] = df_pdsi['data'].dt.month
    df_pdsi['ano'] = df_pdsi['data'].dt.year

    # ========================== VISUALIZAÇÃO PDSI ===========================

    # Gráfico de calor (ano x mês) com intensidade do PDSI
    alt_heat = alt.Chart(df_pdsi).mark_rect().encode(
        x='ano:O',
        y='mes:O',
        color=alt.Color('mean(pdsi):Q', scale=alt.Scale(scheme='redblue', domain=(-5, 5))),
        tooltip=[
            alt.Tooltip('ano:O', title='Year'),
            alt.Tooltip('mes:O', title='Month'),
            alt.Tooltip('mean(pdsi):Q', title='PDSI')
        ]
    ).properties(
        title='Mapa de Calor do Índice de Severidade de Seca Padrão (PDSI)',
        width=600,
        height=300
    )

    # Gráfico de barras temporais (linha do tempo PDSI)
    alt_time = alt.Chart(df_pdsi).mark_bar(size=1).encode(
        x='data:T',
        y='pdsi:Q',
        color=alt.Color('pdsi:Q', scale=alt.Scale(scheme='redblue', domain=(-5, 5))),
        tooltip=[
            alt.Tooltip('data:T', title='Date'),
            alt.Tooltip('pdsi:Q', title='PDSI')
        ]
    ).properties(
        title='Série histórica Índice de Severidade de Seca Padrão (PDSI)',
        width=600,
        height=300
    )

    # ======================= INDICADORES (EXCEDENTE / DÉFICIT HÍDRICO) ==========================

    # Layout padrão do gráfico de indicadores
    layout = go.Layout(
        width=800,
        height=400,
        margin=dict(t=50, b=50, l=50, r=50),
    )

    # Calcula a média da coluna 'water_balance'
    mean_water_balance = df['water_balance'].mean()

    # Remove o sufixo de hora para melhor visualização textual
    df['data'] = pd.to_datetime(df['data']).dt.date

    # Verifica excedente e déficit com base na média
    excess = df['water_balance'] > mean_water_balance
    deficit = df['water_balance'] < mean_water_balance

    # Obtém os extremos de excedente e déficit e suas datas
    max_excess_value = df.loc[excess, 'water_balance'].max()
    max_excess_date = df.loc[df['water_balance'] == max_excess_value, 'data'].values[0]

    min_deficit_value = df.loc[deficit, 'water_balance'].min()
    min_deficit_date = df.loc[df['water_balance'] == min_deficit_value, 'data'].values[0]

    # Criação do gráfico com indicadores
    fig_2 = go.Figure(layout=layout)

    # Indicador: Excedente Hídrico
    fig_2.add_trace(go.Indicator(
        mode="number+delta+gauge",
        value=max_excess_value,  # Maior valor de excedente hídrico
        delta={'reference': mean_water_balance},  # Comparação com a média
        gauge={
            'axis': {'visible': True, 'range': [None, df['water_balance'].max()]},
            'steps': [{'range': [mean_water_balance, df['water_balance'].max()], 'color': "lightgray"}],
            'threshold': {
                'line': {'color': "green", 'width': 4},
                'thickness': 0.75,
                'value': mean_water_balance
            }
        },
        title={"text": f"Excedente hídrico (Data: {max_excess_date})"},
        domain={'x': [0, 0.5], 'y': [0, 1]}
    ))

    # Indicador: Déficit Hídrico
    fig_2.add_trace(go.Indicator(
        mode="number+delta+gauge",
        value=min_deficit_value,  # Menor valor de déficit
        delta={'reference': mean_water_balance},
        gauge={
            'axis': {'visible': True, 'range': [None, df['water_balance'].max()]},
            'steps': [{'range': [df['water_balance'].min(), mean_water_balance], 'color': "lightgray"}],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': mean_water_balance
            }
        },
        title={"text": f"Déficit (Data: {min_deficit_date})"},
        domain={'x': [0.5, 1], 'y': [0, 1]}
    ))


    ############## Dados principais ###################################################

    # Calcular valores máximos, médios e mínimos para ET, Precipitação e PDSI
    max_et = df['ET'].max()
    min_et = df['ET'].min()
    mean_et = df['ET'].mean()

    max_precipitation = df['precipitation'].max()
    min_precipitation = df['precipitation'].min()
    mean_precipitation = df['precipitation'].mean()

    max_pdsi = df_pdsi['pdsi'].max()
    min_pdsi = df_pdsi['pdsi'].min()
    mean_pdsi = df_pdsi['pdsi'].mean()

    # Layout de 3 colunas para mostrar métricas principais
    col1, col2, col3 = st.columns(3)

    # Inserir os valores calculados nas colunas com formato de métricas
    col1.metric("ET", f"Mín: {min_et:.2f}, Méd: {mean_et:.2f}, Máx: {max_et:.2f}", "")
    col2.metric("Precipitação", f"Mín: {min_precipitation:.2f}, Méd: {mean_precipitation:.2f}, Máx: {max_precipitation:.2f}", "")
    col3.metric("PDSI", f"Mín: {min_pdsi:.2f}, Méd: {mean_pdsi:.2f}, Máx: {max_pdsi:.2f}", "")

    # Separador visual
    st.divider()

    # Layout de 3 colunas para visualização dos gráficos e da tabela
    col4, col5, col6 = st.columns([0.3, 0.3, 0.4])

    # Gráfico da série histórica do balanço hídrico
    with col4:
        st.subheader('📈 Balanço Hídrico - Série Histórica')
        st.plotly_chart(fig, use_container_width=True)

    # Exibição da tabela com dados extraídos
    with col5:
        st.subheader("🗃Tabela de dados")
        st.dataframe(df, height=500)

    # Gráfico dos indicadores de excedente e déficit
    with col6:
        st.subheader('📈 Análise Hídrica (P-ET)')
        st.plotly_chart(fig_2, use_container_width=True)

    # Seção PDSI
    st.subheader('Índice de Seca PDSI', divider='blue')

    # Layout com dois gráficos: linha do tempo e mapa de calor
    col7, col8 = st.columns([0.5, 0.5])

    # Gráfico temporal do PDSI
    with col7:
        st.altair_chart(alt_time, theme="streamlit", use_container_width=True)

    # Mapa de calor PDSI por mês/ano
    with col8:
        st.altair_chart(alt_heat, theme="streamlit", use_container_width=True)

    # Seção final: visualização espacial das médias
    st.subheader('Visualização das imagens', divider='blue')

    # Centraliza o mapa na ROI com zoom ajustado
    m.centerObject(roi, 13)

    # Adiciona camadas ao mapa: ROI, PDSI médio, ET médio e Precipitação média
    m.addLayer(roi, {}, 'Região de Interesse')
    m.addLayer(pdsi.mean(), {
        'palette': ['red', 'orange', 'cyan', 'blue'],
        'min': -1,
        'max': 2
    }, 'PDSI')

    m.addLayer(waterBalanceResult.select('ET').mean(), {
        'palette': ['red', 'orange', 'cyan', 'blue'],
        'min': 0,
        'max': 100
    }, 'ET')

    m.addLayer(waterBalanceResult.select('precipitation').mean(), {
        'palette': ['red', 'orange', 'cyan', 'blue'],
        'min': 0,
        'max': 100
    }, 'Precipitation')

    # Expander na barra lateral com resumo das imagens utilizadas
    expander = st.sidebar.expander('Clique para saber mais')
    size_collection = waterBalanceResult.size().getInfo()
    expander.write(
        f"""
        Para a análise de dados de estão sendo utilizadas {size_collection} imagens.
        """
    )

# # Exibe o mapa no Streamlit
# Exibe o mapa no Streamlit apenas se 'm' existir
if 'm' in locals():
    m.to_streamlit()
    
# if st.sidebar.button("🔁 Nova análise"):
#     st.session_state.clear()
#     st.rerun()

st.sidebar.markdown('Desenvolvido por [Christhian Cunha](https://www.linkedin.com/in/christhian-santana-cunha/)') 