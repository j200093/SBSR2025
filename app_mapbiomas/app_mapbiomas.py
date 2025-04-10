import streamlit as st
import geemap
import geemap.foliumap as geemap
import ee
import json
import pandas as pd
import plotly.express as px
 
# Inicialização do Earth Engine

st.set_page_config(layout="wide")
st.title("MapBiomas - Análise de Uso e Cobertura com GeoJSON")

# Sidebar
with st.sidebar:
    st.header("Configurações")
    ano_novo = st.selectbox("📅 Selecione o ano:", list(range(1985, 2024)), index=2023 - 1985)
    geojson_file = st.file_uploader("📂 Faça upload de um GeoJSON", type=["geojson"])
    run_analysis = st.button("🚀 Executar Análise")

# Inicializa o mapa
m = geemap.Map(center=[-14.5, -52], zoom=4)

# Armazena o ano selecionado
if "ano_atual" not in st.session_state:
    st.session_state["ano_atual"] = 2023

if run_analysis:
    st.session_state["ano_atual"] = ano_novo

# Define ano e imagem MapBiomas
ano = st.session_state["ano_atual"]
image_id = "projects/mapbiomas-public/assets/brazil/lulc/collection9/mapbiomas_collection90_integration_v1"
image = ee.Image(image_id)
lulc = image.select(f"classification_{ano}")

# Paleta personalizada (do usuário)
palette = [
    "#ffffff", "#32a65e", "#32a65e", "#1f8d49", "#7dc975", "#04381d", "#026975", "#000000",
    "#000000", "#7a6c00", "#ad975a", "#519799", "#d6bc74", "#d89f5c", "#FFFFB2", "#edde8e",
    "#000000", "#000000", "#f5b3c8", "#C27BA0", "#db7093", "#ffefc3", "#db4d4f", "#ffa07a",
    "#d4271e", "#db4d4f", "#0000FF", "#000000", "#000000", "#ffaa5f", "#9c0027", "#091077",
    "#fc8114", "#2532e4", "#93dfe6", "#9065d0", "#d082de", "#000000", "#000000", "#f5b3c8",
    "#c71585", "#f54ca9", "#cca0d4", "#dbd26b", "#807a40", "#e04cfa", "#d68fe2", "#9932cc",
    "#e6ccff", "#02d659", "#ad5100", "#000000", "#000000", "#000000", "#000000", "#000000",
    "#000000", "#CC66FF", "#FF6666", "#006400", "#8d9e8b", "#f5d5d5", "#ff69b4", "#ebf8b5",
    "#000000", "#000000", "#91ff36", "#7dc975", "#e97a7a", "#0fffe3"
]

vis_params = {
    'min': 0,
    'max': 69,
    'palette': palette
}

legenda = pd.DataFrame([
    {"Classe": 1, "Nome": "Floresta", "Cor": "#1f8d49"},
    {"Classe": 3, "Nome": "Formação Florestal", "Cor": "#1f8d49"},
    {"Classe": 4, "Nome": "Formação Savânica", "Cor": "#7dc975"},
    {"Classe": 5, "Nome": "Mangue", "Cor": "#04381d"},
    {"Classe": 6, "Nome": "Floresta Alagável", "Cor": "#026975"},
    {"Classe": 49, "Nome": "Restinga Arbórea", "Cor": "#02d659"},
    {"Classe": 10, "Nome": "Vegetação Herbácea e Arbustiva", "Cor": "#ad975a"},
    {"Classe": 11, "Nome": "Campo Alagado e Área Pantanosa", "Cor": "#519799"},
    {"Classe": 12, "Nome": "Formação Campestre", "Cor": "#d6bc74"},
    {"Classe": 32, "Nome": "Apicum", "Cor": "#fc8114"},
    {"Classe": 29, "Nome": "Afloramento Rochoso", "Cor": "#ffaa5f"},
    {"Classe": 50, "Nome": "Restinga Herbácea", "Cor": "#ad5100"},
    {"Classe": 14, "Nome": "Agropecuária", "Cor": "#FFFFB2"},
    {"Classe": 15, "Nome": "Pastagem", "Cor": "#edde8e"},
    {"Classe": 18, "Nome": "Agricultura", "Cor": "#E974ED"},
    {"Classe": 19, "Nome": "Lavoura Temporária", "Cor": "#C27BA0"},
    {"Classe": 39, "Nome": "Soja", "Cor": "#f5b3c8"},
    {"Classe": 20, "Nome": "Cana", "Cor": "#db7093"},
    {"Classe": 40, "Nome": "Arroz", "Cor": "#c71585"},
    {"Classe": 62, "Nome": "Algodão (beta)", "Cor": "#ff69b4"},
    {"Classe": 41, "Nome": "Outras Lavouras Temporárias", "Cor": "#f54ca9"},
    {"Classe": 36, "Nome": "Lavoura Perene", "Cor": "#d082de"},
    {"Classe": 46, "Nome": "Café", "Cor": "#d68fe2"},
    {"Classe": 47, "Nome": "Citrus", "Cor": "#9932cc"},
    {"Classe": 35, "Nome": "Dendê", "Cor": "#9065d0"},
    {"Classe": 48, "Nome": "Outras Lavouras Perenes", "Cor": "#e6ccff"},
    {"Classe": 9, "Nome": "Silvicultura", "Cor": "#7a5900"},
    {"Classe": 21, "Nome": "Mosaico de Usos", "Cor": "#ffefc3"},
    {"Classe": 22, "Nome": "Área não Vegetada", "Cor": "#d4271e"},
    {"Classe": 23, "Nome": "Praia, Duna e Areal", "Cor": "#ffa07a"},
    {"Classe": 24, "Nome": "Área Urbanizada", "Cor": "#d4271e"},
    {"Classe": 30, "Nome": "Mineração", "Cor": "#9c0027"},
    {"Classe": 25, "Nome": "Outras Áreas não Vegetadas", "Cor": "#db4d4f"},
    {"Classe": 26, "Nome": "Corpo D'água", "Cor": "#0000FF"},
    {"Classe": 33, "Nome": "Rio, Lago e Oceano", "Cor": "#2532e4"},
    {"Classe": 31, "Nome": "Aquicultura", "Cor": "#091077"},
    {"Classe": 27, "Nome": "Não Observado", "Cor": "#ffffff"},
])



if geojson_file is not None and run_analysis:
    try:
        geojson_data = json.load(geojson_file)
        fc = geemap.geojson_to_ee(geojson_data)
        m.addLayer(fc, {}, "ROI")
        m.centerObject(fc, zoom=10)

        # Recorta a imagem pela ROI
        lulc_clipped = lulc.clip(fc)
        m.addLayer(lulc_clipped, vis_params, f'MapBiomas Col 9 - {ano} (Recortado)')

        # Calcula área por classe
        pixel_area = ee.Image.pixelArea().divide(1e4)  # ha
        image_area = pixel_area.addBands(lulc)
        area_por_classe = image_area.reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName='class'),
            geometry=fc.geometry(),
            scale=30,
            maxPixels=1e13
        )

        stats = area_por_classe.getInfo()
        grupos = stats['groups']
        df = pd.DataFrame(grupos)
        df = df.rename(columns={"class": "Classe", "sum": "Área (ha)"})
        df = df.sort_values("Área (ha)", ascending=False)
        df = df.merge(legenda, on="Classe", how="left")

        st.markdown("### 📊 Gráfico de Barras - Área por Classe")
        fig_bar = px.bar(df, x="Nome", y="Área (ha)", color="Nome",
                 color_discrete_map=dict(zip(df["Nome"], df["Cor"])))
        st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("### 🥧 Gráfico de Pizza - Área por Classe")
        fig_pie = px.pie(df, values="Área (ha)", names="Nome",
                 color="Nome", color_discrete_map=dict(zip(df["Nome"], df["Cor"])))
        st.plotly_chart(fig_pie, use_container_width=True)

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")

# Camada de uso e cobertura
m.addLayer(lulc, vis_params, f'MapBiomas Col 9 - {ano}')
m.to_streamlit(height=600)
