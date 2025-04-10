import streamlit as st
from streamlit_folium import folium_static
from streamlit_folium import st_folium
import folium

import pandas as pd
import plotly.express as px

import geopandas as gpd

from proc import ler_geodataframe, selecionar_imovel_car, inserir_geojson_folium, mostrar_status

# Configurações iniciais
st.set_page_config(page_title="Embargos", layout="wide")
# page_title="Embargos" -  Título da aba do navegador
#layout="wide" - Define o layout da página como "wide" (largura total)

# Caminho para o GeoPackage
gpkg_file = "./car_embargos.gpkg"
# Informar a coluna com a matrícula do imóvel rural
coluna_matricula_imovel = 'cod_imovel'

# Leitura dos dados do CAR
area_imovel = ler_geodataframe(gpkg_file, 'area_imovel')
# Leitura dos dados Embargos IBAMA
embargos_ibama = ler_geodataframe(gpkg_file, 'embargos_ibama')
# Leitura dos dados Embargos ICMBio
embargos_icmbio = ler_geodataframe(gpkg_file, 'embargos_icmbio')

# Selecionar o códigos dos imóveis do INCRA
cod_imoveis_car = area_imovel[coluna_matricula_imovel].unique()

# Carregar os dados
st.sidebar.title("Filtros")

# Criar o selectbox com os códigos dos imóveis do INCRA
codigo_imo_car_selecionado = st.sidebar.selectbox("Escolha o imóvel:", cod_imoveis_car)

# Escrever no sidebar o código do imóvel selecionado
st.sidebar.write(f"Código do imóvel selecionado: {codigo_imo_car_selecionado}")
# Selecionar o imóvel do INCRA e retorna as coordenadas envolventes do imóvel
gdf_car_selecionado, centro_lat, centro_lon, miny, maxy, minx, maxx = selecionar_imovel_car(area_imovel, codigo_imo_car_selecionado, coluna_matricula_imovel)

# Selecionar os embargos
gdf_embargo_ibama_selecionado = embargos_ibama[embargos_ibama[coluna_matricula_imovel]==codigo_imo_car_selecionado].copy()
gdf_embargo_icmbio_selecionado = embargos_icmbio[embargos_icmbio[coluna_matricula_imovel]==codigo_imo_car_selecionado].copy()

# Título centralizado usando HTML e CSS
st.markdown(
    """
    <h1 style='text-align: center; color: darkblue;'>Painel de Monitoramento de Embargos no CAR 🌍</h1>
    """,
    unsafe_allow_html=True
)

# Criar e exibir o mapa
st.subheader("Mapa Interativo")

# Centraliza no centroide dos dados do Área Imóvel
centro_x = area_imovel.geometry.centroid.x.mean()
centro_y = area_imovel.geometry.centroid.y.mean()

# Iniciando o mapa Folium com CAR
mapa = folium.Map(location=[centro_y, centro_x], zoom_start=10)

# Gerar o mapa com dados do CAR
mapa = inserir_geojson_folium(area_imovel[[coluna_matricula_imovel,'geometry']], coluna_matricula_imovel
                              ,'Código do Imóvel'
                              ,'Área do Imóvel'
                              ,'white'
                              ,mapa)

# Gerar o mapa com CAR selecionado
mapa = inserir_geojson_folium(gdf_car_selecionado[[coluna_matricula_imovel,'geometry']], coluna_matricula_imovel
                              ,'Código do Imóvel'
                              ,'CAR selecionado'
                              ,'yellow'
                              ,mapa)

# Gerar o mampa com Emabrgos IBAMA
mapa = inserir_geojson_folium(embargos_ibama[[coluna_matricula_imovel,'geometry']], coluna_matricula_imovel
                              ,'Código do Imóvel'
                              ,'Embargos IBAMA'
                              ,'red'
                              ,mapa)

# Gerar o mampa com Emabrgos ICMBio
mapa = inserir_geojson_folium(embargos_icmbio[[coluna_matricula_imovel,'geometry']], coluna_matricula_imovel
                              ,'Código do Imóvel'
                              ,'Embargos ICMBio'
                              ,'orange'
                              ,mapa)
# Adiciona controle de camadas
folium.LayerControl().add_to(mapa)

# Ajustar o mapa para os limites do polígono
mapa.fit_bounds([[miny, minx], [maxy, maxx]])
# Exibir o mapa
st_folium(mapa, use_container_width=True, height=500)



# Sidebar
st.sidebar.title("📊 Conformidade")

# Função para exibir status com emoji
def mostrar_status(nome, status):
    emoji = "✅" if status == 0 else "❌"
    st.sidebar.write(f"{emoji} {nome}")

# Exibir status
mostrar_status(" Embargos IBAMA", gdf_embargo_ibama_selecionado.shape[0])
mostrar_status(" Embargos ICMBio", gdf_embargo_icmbio_selecionado.shape[0])

st.subheader("Embargos IBAMA")
# Avaliar se a tabela do IBAMA não está vazia 
if gdf_embargo_ibama_selecionado.empty:
    st.write("Nenhum embargo do IBAMA encontrado para o imóvel selecionado.")
else:
    # Exibir tabela com os dados do imóvel selecionado
    st.dataframe(gdf_embargo_ibama_selecionado, use_container_width=True)

st.subheader("Embargos ICMBio")
# Avaliar se a tabela do ICMBio não está vazia
if gdf_embargo_icmbio_selecionado.empty:
    st.write("Nenhum embargo do ICMBio encontrado para o imóvel selecionado.")
else:
    # Exibir tabela com os dados do imóvel selecionado
    st.dataframe(gdf_embargo_icmbio_selecionado, use_container_width=True)
