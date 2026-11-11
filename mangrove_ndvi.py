import os, time
import ee
from dotenv import load_dotenv

load_dotenv()
ee.Initialize(project=os.getenv('EE_PROJECT_ID'))

boxes = {
    'Sundarbans': ee.Geometry.Rectangle([88.60, 21.70, 88.90, 21.95]),
    'Coringa':    ee.Geometry.Rectangle([82.25, 16.75, 82.40, 16.95]),
}

def remove_clouds(img):
    scl = img.select('SCL')
    clear = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
    return img.updateMask(clear)

def ndvi_images(box, a, b):
    return (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(box).filterDate(a, b).map(remove_clouds)
            .map(lambda im: im.normalizedDifference(['B8', 'B4']).rename('ndvi')))

def tree_mask(box):
    # typical greenness across 2019: trees stay well above water and mudflat
    typical = ndvi_images(box, '2019-01-01', '2020-01-01').median()
    return typical.gt(0.6)

def ndvi_for_month(box, mask, year, month):
    a = ee.Date.fromYMD(year, month, 1)
    b = a.advance(1, 'month')
    green = ndvi_images(box, a, b).median().updateMask(mask)
    return green.reduceRegion(
        ee.Reducer.mean(), box, 30, maxPixels=1e9, bestEffort=True
    ).get('ndvi').getInfo()

for name, box in boxes.items():
    mask = tree_mask(box)
    ha = (mask.multiply(ee.Image.pixelArea()).reduceRegion(
          ee.Reducer.sum(), box, 30, maxPixels=1e9, bestEffort=True)
          .get('ndvi').getInfo()) / 10000
    print(f"\n{name}: {ha:,.0f} hectares of dense evergreen trees")
    for year in (2019, 2020, 2021):
        for month in range(1, 13):
            try:
                v = ndvi_for_month(box, mask, year, month)
            except Exception:
                time.sleep(5)
                v = ndvi_for_month(box, mask, year, month)
            shown = f"{v:.3f}" if v is not None else "no data"
            print(f"  {year}-{month:02d}  {shown}", flush=True)