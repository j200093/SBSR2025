import folium
import geopandas as gpd

import streamlit as st


@st.cache_data
def ler_geodataframe(caminho_gpkg, tabela):
    """
    Lê os dados do GeoPackage e retorna um GeoDataFrame.
    """
    query = f"SELECT * FROM {tabela}"
    gdf = gpd.read_file(caminho_gpkg, sql=query, engine="fiona")
    return gdf


def selecionar_imovel_car (gdf_car, codigo_imovel, coluna_matricula_imovel):
    
    """Selecionar o imóvel do INCRA com base no código.

    Args:
        gdf_incra (GeoDataFrame): GeoDataFrame com os dados do INCRA.
        codigo_imovel (String): Código do imóvel a ser selecionado.

    Returns:
        gdf_incra_selecionado, centro_lat, centro_lon, miny, maxy, minx, maxx
    """
    # Selecionar o CAR considerando selectbox
    gdf_car_selecionado = gdf_car[gdf_car[coluna_matricula_imovel]==codigo_imovel].copy()

    # Calcular o Bounding Box do polígono
    bounds = gdf_car_selecionado.geometry.total_bounds
    # Coords do Bounding Box
    minx, miny, maxx, maxy = bounds

    # Definir o centro do mapa com base no polígono selecionado
    centro_lat = (miny + maxy) / 2
    centro_lon = (minx + maxx) / 2

    return gdf_car_selecionado, centro_lat, centro_lon, miny, maxy, minx, maxx



def inserir_geojson_folium (gdf, nome_coluna
                            ,alias_coluna
                            ,nome_camada
                            ,cor_preenchimento
                            ,mapa):
    """
    Cria um mapa Folium a partir de um GeoDataFrame.
    """


    # Adiciona a camada GeoJSON ao mapa
    # Adicionar a camada de Imóveis Rurais
    folium.GeoJson(
        data=gdf,  # GeoDataFrame convertido diretamente em GeoJson
        name = nome_camada,  # Nome da camada no LayerControl
        tooltip=folium.GeoJsonTooltip(  # Configurar tooltip
            fields=[nome_coluna],  # Coluna(s) para mostrar no tooltip
            aliases=[alias_coluna+':'],  # Nomes amigáveis no tooltip
            localize=True
        ),
        style_function=lambda x: {
            'fillColor': cor_preenchimento,  # Cor de preenchimento
            'color': 'black',       # Cor das bordas
            'weight': 1,            # Largura das bordas
            'fillOpacity': 0.6      # Opacidade do preenchimento
        }
    ).add_to(mapa)

   

    return mapa

# Função para exibir status com emoji
def mostrar_status(nome, status):
    emoji = "✅" if status == 0 else "❌"
    
