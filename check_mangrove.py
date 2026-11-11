import os
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

for name, box in boxes.items():
    imgs = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(box).filterDate('2019-01-01', '2020-01-01')
            .map(remove_clouds)
            .map(lambda im: im.normalizedDifference(['B8', 'B4']).rename('ndvi')))

    print(f"\n{name}")
    print("  images found:", imgs.size().getInfo())

    stats = imgs.median().reduceRegion(
        ee.Reducer.percentile([10, 50, 75, 90, 95]),
        box, 30, maxPixels=1e9, bestEffort=True).getInfo()
    print("  greenness spread across the box:")
    for k, v in sorted(stats.items()):
        print(f"    {k}: {v:.3f}" if v is not None else f"    {k}: none")