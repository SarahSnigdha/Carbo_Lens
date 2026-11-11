import os
import ee
from dotenv import load_dotenv

load_dotenv()
ee.Initialize(project=os.getenv('EE_PROJECT_ID'))

SITES = {
    'Similipal': ee.Geometry.Rectangle([86.07, 21.47, 86.62, 22.13]),
    'Coringa':   ee.Geometry.Rectangle([82.25, 16.75, 82.40, 16.95]),
    'Borneo':    ee.Geometry.Rectangle([113.0, -1.0, 113.5, -0.5]),
}

# ---------- RADD: which regions exist, and do they touch our sites ----------
radd = ee.ImageCollection('projects/radar-wur/raddalert/v1')
print("RADD geographies:", radd.aggregate_array('geography').distinct().getInfo())
print("RADD layers:", radd.aggregate_array('layer').distinct().getInfo())

for name, geom in SITES.items():
    n = radd.filterBounds(geom).size().getInfo()
    print(f"  RADD tiles over {name}: {n}")

# ---------- GLAD: which years, and coverage at sites ----------
glad = ee.ImageCollection('projects/glad/alert/UpdResult')
print("\nGLAD band sets seen:", glad.limit(3).aggregate_array('system:band_names').getInfo())

for year_band in ['alertDate25', 'alertDate26']:
    print(f"\n  --- {year_band} ---")
    for name, geom in SITES.items():
        try:
            img = glad.select([year_band]).filterBounds(geom).mosaic()
            stats = (img.gt(0).selfMask()
                     .reduceRegion(ee.Reducer.count(), geom, 100, maxPixels=1e9)
                     .getInfo())
            print(f"    {name:10s} alert pixels: {stats}")
        except Exception as e:
            print(f"    {name:10s} FAIL: {str(e)[:70]}")