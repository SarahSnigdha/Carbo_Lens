import os
import ee
from dotenv import load_dotenv

load_dotenv()
ee.Initialize(project=os.getenv('EE_PROJECT_ID'))

# A box around Similipal (longitude, latitude)
similipal = ee.Geometry.Rectangle([86.07, 21.47, 86.62, 22.13])

# NASA fire data inside Earth Engine
fires = ee.ImageCollection('FIRMS').select('T21')

print("Month    Fire spots in Similipal")
for year in range(2017, 2025):
    month = 3
    start = ee.Date.fromYMD(year, month, 1)
    end = start.advance(1, 'month')
    img = fires.filterDate(start, end).max()
    count = img.reduceRegion(ee.Reducer.count(), similipal, 1000).get('T21')
    print(f"{year}-03   {count.getInfo()}")