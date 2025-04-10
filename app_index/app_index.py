import streamlit as st
import streamlit_folium
from streamlit_folium import st_folium
import geemap
import geemap.foliumap as geemap
import ee
import plotly.express as px
import folium
import pandas as pd
import geopandas as gpd
from datetime import datetime
import json
from utils_gee import maskCloudAndShadowsSR, add_indices


# Autenticação com Earth Engine
# service_account = 'my-service-account@...gserviceaccount.com'
# credentials = ee.ServiceAccountCredentials(service_account, 'ee-scriptsremoteambgeo-040e397e0cc0.json')
# ee.Initialize(credentials)
# Inicializa um mapa apenas para garantir autenticação do Earth Engine
auth_map = geemap.Map()
# Configuração da página
st.set_page_config(layout="wide")
st.title('Aplicativo para seleção de imagens, cálculo de índices e download das imagens')
st.markdown(""" 
#### O APP foi desenvolvido para que o usuário possa carregar a região de interesse, definir o período e visualizar o diferentes índices de vegetação e água. 
A aplicação processa imagens do Sentinel 2, Dataset disponível no Google Earth Engine. 
Após carregar o arquivo é possível inspecionar quantas imagens existem na região de interesse, selecionar as datas que deseja visualizar e ativar os índices no painel lateral.
""")

##Defina a região de interesse.
roi = None
m = geemap.Map(height=800)

# Upload do arquivo GeoJSON
st.sidebar.subheader("Carregue um arquivo no formato GeoJSON:")
uploaded_file = st.sidebar.file_uploader("Faça o upload da sua área de estudo", type=["geojson"])
st.sidebar.markdown("""### Para criar o arquivo **GeoJSON** use o site [geojson.io](https://geojson.io/#new&map=2/0/20).""")

if uploaded_file is not None:
    gdf = gpd.read_file(uploaded_file)
    shp_json = gdf.to_json()
    f_json = json.loads(shp_json)['features']
    roi = ee.FeatureCollection(f_json)
    st.sidebar.success("Arquivo carregado com sucesso!")

point = ee.Geometry.Point(-45.259679, -17.871838)
m.centerObject(point, 8)
m.setOptions("HYBRID")

start_date = st.sidebar.date_input("Selecione a data inicial", datetime(2024, 1, 1))
end_date = st.sidebar.date_input("Selecione a data final", datetime.now())
cloud_percentage_limit = st.sidebar.slider("Limite de percentual de nuvens", 0, 100, 5)

if roi is not None:
  # Função de nuvens, fator de escala e clip
    def maskCloudAndShadowsSR(image):
        cloudProb = image.select('MSK_CLDPRB');
        snowProb = image.select('MSK_SNWPRB');
        cloud = cloudProb.lt(5)
        snow = snowProb.lt(5)
        scl = image.select('SCL')
        shadow = scl.eq(3)  # 3 = cloud shadow
        cirrus = scl.eq(10)  # 10 = cirrus
        # Probabilidade de nuvem inferior a 5% ou classificação de sombra de nuvem
        mask = (cloud.And(snow)).And(cirrus.neq(1)).And(shadow.neq(1));
        return image.updateMask(mask)\
            .select("B.*")\
            .divide(10000)\
            .clip(roi)\
            .copyProperties(image, image.propertyNames())

    # Cálculo do índice
    def indice(image):
        ndvi = image.normalizedDifference(['B8','B4']).rename('ndvi')
        ndre = image.normalizedDifference(['B8','B5']).rename('ndre') 
        evi = image.expression(
            'G * ((NIR - RED) / (NIR + C1 * RED - C2 * BLUE + L))',
            {
                'G': 2.5,
                'NIR': image.select('B8'),
                'RED': image.select('B4'),
                'BLUE': image.select('B2'),
                'C1': 6.0,
                'C2': 7.5,
                'L': 1.0
            }
        ).rename('evi')
        mndwi = image.normalizedDifference(['B3','B11']).rename('mndwi')
        ndwi = image.normalizedDifference(['B3','B8']).rename('ndwi')
        ndmi = image.normalizedDifference(['B8','B11']).rename('ndmi')
        ndpi = image.normalizedDifference(['B11','B3']).rename('ndpi')
        spri = image.normalizedDifference(['B2','B3']).rename('spri')
             
        savi = image.expression(
                '((NIR - RED) / (NIR + RED + L)) * (1 + L)',
                {
                    'NIR': image.select('B8'), # Infravermelho próximo
                    'RED': image.select('B4'), # Vermelho
                    'L': 0.5 # Fator de ajuste do solo (0.5 para vegetação)
                }
            ).rename('savi')
        
        return image.addBands([ndvi, ndre,evi,ndwi,mndwi,ndmi,ndpi,spri,savi]).set({'data': image.date().format('yyyy-MM-dd')})

           
    # Coleção de imagens 
    collection = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")\
                    .filterBounds(roi)\
                    .filter(ee.Filter.date(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))\
                    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_percentage_limit))\
                    .map(maskCloudAndShadowsSR)\
                    .map(indice)
        # Criar a tabela usando os dados da coleção filtrada
    data_table = pd.DataFrame({
        "Data": collection.aggregate_array("data").getInfo(),
        "Percentual de Nuvens": collection.aggregate_array("CLOUDY_PIXEL_PERCENTAGE").getInfo(),
        "ID": collection.aggregate_array("system:id").getInfo()
    })
    
      # ##Data Frame
    # expander.write(data_table)
    st.divider()
    # Função para aplicar a redução por regiões para toda a coleção usando map
    def reduce_region_for_collection(img):
        # Obtém a data da imagem
        date = img.date().format('yyyy-MM-dd')

        # Aplica a redução por regiões para a imagem
        stats = img.reduceRegions(
            collection=roi,
            reducer=ee.Reducer.mean(),
            scale=10  # Defina a escala apropriada para sua aplicação
        )

        # Adiciona a data à propriedade 'data'
        stats = stats.map(lambda f: f.set('data', date))

        return stats

    # Aplica a redução por regiões para toda a coleção usando map
    bands = ['ndvi', 'ndre','evi','ndwi','mndwi','ndmi','ndpi','spri','savi']
    stats_collection = collection.select(bands).map(reduce_region_for_collection)

    # Converte para df
    df = geemap.ee_to_df(stats_collection.flatten())

    # Adiciona a data como coluna no formato datetime
    df['datetime'] = pd.to_datetime(df['data'], format='%Y-%m-%d')

    # Verificar se todas as colunas necessárias estão presentes e adicionar colunas ausentes com NaN
    # Plotar gráfico usando Plotly Express
    fig = px.line(df, x='datetime', y=bands, title='Série Temporal de Índices', 
                labels={'value': 'Índice', 'variable': 'Tipo de Índice'},
                line_dash='variable', line_group='variable')
    
    fig_bar = px.bar(df, x='datetime', y=bands, 
                 title='Gráfico de Barras de Índices',
                 labels={'value': 'Índice', 'variable': 'Tipo de Índice'},
                 barmode='group')

    
    ##criando coluna 1 e 2 
    col1, col2 = st.columns([0.6,0.4])
    # Exibir o gráfico no Streamlit
    with col1:
         tab1, tab2 = st.tabs(["📈 Gráfico de Linha", "📈 Imagens Disponíveis"])
         tab1.subheader('Gráfico')
         tab1.plotly_chart(fig, use_container_width=True)
         ##Tabela 2 
         tab2.subheader("Tabela de Informações")
         tab2.write(data_table)
        

    with col2:
        tab3, tab4 = st.tabs(["📈 Gráfico de Linha", "📈 Imagens Disponíveis"])
        tab3.subheader('Gráfico')
        tab3.plotly_chart(fig_bar, use_container_width=True)
        tab4.subheader('DataFrame')
        tab4.dataframe(df.style.set_table_styles([{'selector': 'table', 'props': [('width', '400px')]}]))
    
    st.divider()
    

    contour_image = ee.Image().byte().paint(featureCollection=roi, color=1, width=2)
    m.addLayer(contour_image, {'palette': 'FF0000'}, 'Região de Interesse')
    m.centerObject(roi, 13)
    
     # ================== ADICIONAR MOSAICO DE ÍNDICE ==================
    # Lista de índices de vegetação e de água
    vegetation_indices = ['ndvi', 'evi', 'savi']
    water_indices = ['ndwi', 'mndwi', 'ndmi']

    # Últimos 10 dias do período
    end_ee = ee.Date(end_date.strftime('%Y-%m-%d'))
    start_ee = end_ee.advance(-10, 'day')

    # Filtra e processa a coleção recente
    recent_collection = collection.filterDate(start_ee, end_ee)

    # Escolher o índice para visualização (você pode tornar isso interativo se quiser)
    selected_index = st.sidebar.selectbox("📌 Índice para visualização espacial:",
                                          vegetation_indices + water_indices, index=0)

    # Calcular imagem média para esse índice
    mean_index_image = recent_collection.select(selected_index).mean()

    # Paleta e estilo de visualização
    if selected_index in vegetation_indices:
        palette = ['red', 'yellow', 'green']
    elif selected_index in water_indices:
        palette = ['cyan', 'blue', 'darkblue']
    else:
        palette = ['gray']  # fallback

    # Adicionar camada ao mapa
    m.addLayer(mean_index_image, {
        'min': -1,
        'max': 1,
        'palette': palette
    }, f'{selected_index.upper()} - Média últimos 10 dias')

m.to_streamlit()

st.sidebar.markdown('Desenvolvido por [Christhian Cunha](https://www.linkedin.com/in/christhian-santana-cunha/)')
st.sidebar.markdown('Conheça nossas formações [AmbGEO](https://ambgeo.com/)')