import os
import ee
from dotenv import load_dotenv

load_dotenv()
ee.Initialize(project=os.getenv('EE_PROJECT_ID'))

print("Earth Engine OK:", ee.Number(1).add(1).getInfo())

img = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterDate('2023-01-01', '2023-02-01') \
        .first()
print("Sentinel-2 OK:", img.get('system:index').getInfo())