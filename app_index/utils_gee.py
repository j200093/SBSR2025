import ee

def maskCloudAndShadowsSR(image, roi):
    cloudProb = image.select('MSK_CLDPRB')
    snowProb = image.select('MSK_SNWPRB')
    cloud = cloudProb.lt(5)
    snow = snowProb.lt(5)
    scl = image.select('SCL')
    shadow = scl.eq(3)   # sombra
    cirrus = scl.eq(10)  # cirros

    mask = (cloud.And(snow)).And(cirrus.neq(1)).And(shadow.neq(1))
    
    return image.updateMask(mask) \
                .select("B.*") \
                .divide(10000) \
                .clip(roi) \
                .copyProperties(image, image.propertyNames())

def add_indices(image):
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
    ndwi  = image.normalizedDifference(['B3','B8']).rename('ndwi')
    ndmi  = image.normalizedDifference(['B8','B11']).rename('ndmi')
    ndpi  = image.normalizedDifference(['B11','B3']).rename('ndpi')
    spri  = image.normalizedDifference(['B2','B3']).rename('spri')
    
    savi = image.expression(
        '((NIR - RED) / (NIR + RED + L)) * (1 + L)',
        {
            'NIR': image.select('B8'),
            'RED': image.select('B4'),
            'L': 0.5
        }
    ).rename('savi')
    
    return image.addBands([ndvi, ndre, evi, ndwi, mndwi, ndmi, ndpi, spri, savi]) \
                .set({'data': image.date().format('yyyy-MM-dd')})
