# utils_geo.py

import os
import io
import tempfile
from zipfile import ZipFile
 
import fiona
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, MultiPolygon


def convert_3D_2D(geometry):
    """
    Converte uma geometria 3D em 2D.
    """
    if geometry.has_z:
        if geometry.geom_type == 'Polygon':
            return Polygon([(x, y) for x, y, z in geometry.exterior.coords])
        elif geometry.geom_type == 'MultiPolygon':
            new_polygons = []
            for polygon in geometry.geoms:
                new_polygons.append(Polygon([(x, y) for x, y, z in polygon.exterior.coords]))
            return MultiPolygon(new_polygons)
    return geometry


def convert_to_geodf(uploaded_file):
    """
    Converte arquivos geográficos enviados (GeoJSON, SHP, KML, KMZ, GPKG, ZIP) para GeoDataFrame 2D.
    """
    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
    gdf_list = []

    # Suporte extra para drivers KML
    fiona.drvsupport.supported_drivers['KML'] = 'rw'
    fiona.drvsupport.supported_drivers['libkml'] = 'rw'
    fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'

    # KMZ (extração de arquivos internos)
    if file_extension == '.kmz':
        with tempfile.TemporaryDirectory() as extraction_dir:
            with ZipFile(io.BytesIO(uploaded_file.getvalue()), 'r') as kmz:
                kmz.extractall(extraction_dir)
            for filename in os.listdir(extraction_dir):
                if filename.lower().endswith('.kml'):
                    kml_file_path = os.path.join(extraction_dir, filename)
                    for layer in fiona.listlayers(kml_file_path):
                        gdf = gpd.read_file(kml_file_path, layer=layer, driver='LIBKML')
                        gdf_list.append(gdf)

    # ZIP com shapefile completo
    elif file_extension == '.zip':
        with tempfile.TemporaryDirectory() as zip_dir:
            with ZipFile(io.BytesIO(uploaded_file.getvalue()), 'r') as zip_ref:
                zip_ref.extractall(zip_dir)
            # Procura o .shp dentro da pasta descompactada
            for file in os.listdir(zip_dir):
                if file.endswith('.shp'):
                    shp_path = os.path.join(zip_dir, file)
                    gdf = gpd.read_file(shp_path)
                    gdf_list.append(gdf)

    elif file_extension in ['.kml', '.gpkg', '.geojson']:
        gdf = gpd.read_file(io.BytesIO(uploaded_file.getvalue()))
        gdf_list = [gdf]

    # OBS: não suportar .shp diretamente sem os demais componentes
    elif file_extension == '.shp':
        raise ValueError("Um arquivo .shp isolado não é suportado. Por favor, envie todos os arquivos em um .zip.")

    if gdf_list:
        combined_gdf = pd.concat(gdf_list, ignore_index=True)
        
        # Verifica e ajusta CRS
        if combined_gdf.crs is None:
            combined_gdf = gpd.GeoDataFrame(combined_gdf, crs="EPSG:4326")
        else:
            combined_gdf = combined_gdf.to_crs("EPSG:4326")

        # Remove coordenada Z se existir
        combined_gdf['geometry'] = combined_gdf['geometry'].apply(convert_3D_2D)

        return combined_gdf
    else:
        return None
