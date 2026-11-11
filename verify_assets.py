import os
import ee
from dotenv import load_dotenv

load_dotenv()
ee.Initialize(project=os.getenv('EE_PROJECT_ID'))

# Similipal box + a date range, to prove data exists, not just that the asset loads
AOI = ee.Geometry.Rectangle([86.07, 21.47, 86.62, 22.13])
START, END = '2023-01-01', '2023-04-01'

COLLECTIONS = {
    'Sentinel-2':      'COPERNICUS/S2_SR_HARMONIZED',
    'Dynamic World':   'GOOGLE/DYNAMICWORLD/V1',
    'CHIRPS daily':    'UCSB-CHG/CHIRPS/DAILY',
    'ERA5-Land hourly':'ECMWF/ERA5_LAND/HOURLY',
    'ERA5-Land monthly':'ECMWF/ERA5_LAND/MONTHLY_AGGR',
    'FIRMS':           'FIRMS',
}

IMAGES = {
    'Hansen 2025':     'UMD/hansen/global_forest_change_2025_v1_13',
    'Hansen 2023':     'UMD/hansen/global_forest_change_2023_v1_11',
    'SRTM elevation':  'USGS/SRTMGL1_003',
}

OTHER = {
    'GLAD-L alerts':   ('ImageCollection', 'projects/glad/alert/UpdResult'),
    'RADD alerts':     ('ImageCollection', 'projects/radar-wur/raddalert/v1'),
    'GMW mangroves':   ('ImageCollection', 'JAXA/ALOS/PALSAR/YEARLY/FNF4'),
}

def check(name, kind, path, filt=True):
    try:
        if kind == 'ImageCollection':
            c = ee.ImageCollection(path).filterBounds(AOI)
            if filt:
                c = c.filterDate(START, END)
            n = c.size().getInfo()
            print(f"  PASS  {name:20s} {n} images in test window")
        else:
            bands = ee.Image(path).bandNames().getInfo()
            print(f"  PASS  {name:20s} bands: {bands[:4]}")
    except Exception as e:
        print(f"  FAIL  {name:20s} {str(e)[:90]}")

print("\nImageCollections")
for n, p in COLLECTIONS.items():
    check(n, 'ImageCollection', p)

print("\nImages")
for n, p in IMAGES.items():
    check(n, 'Image', p)

print("\nAlerts and masks (these are the uncertain ones)")
for n, (k, p) in OTHER.items():
    check(n, k, p, filt=False)