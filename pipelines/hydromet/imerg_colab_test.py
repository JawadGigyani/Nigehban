"""IMERG access test for Google Earth Engine. Run it in Google Colab, not locally.

Steps (in a Colab cell):
    !pip -q install earthengine-api
    # paste this file into a cell, set PROJECT, run it
It asks you to sign in with Google once. PROJECT is a Google Cloud project
registered for Earth Engine (non-commercial use is free:
https://code.earthengine.google.com/register).

It prints daily IMERG rain (mm) over Buner district for 13–16 Aug 2025 and
how long the request took. If it fails or asks for billing, IMERG is dropped
for the MVP (ERA5 and forecasts are enough).
"""

import time

import ee

PROJECT = "your-gee-project-id"

ee.Authenticate()
ee.Initialize(project=PROJECT)

buner = ee.Geometry.Rectangle([72.25, 34.35, 72.85, 34.70])
started = time.time()
collection = (ee.ImageCollection("NASA/GPM_L3/IMERG_V07")
              .filterDate("2025-08-13", "2025-08-17")
              .select("precipitation"))  # mm/hr, half-hourly


def daily(day):
    start = ee.Date(day)
    total = collection.filterDate(start, start.advance(1, "day")).sum().multiply(0.5)
    value = total.reduceRegion(ee.Reducer.mean(), buner, 10000).get("precipitation")
    return ee.Feature(None, {"date": start.format("YYYY-MM-dd"), "mm": value})


days = ee.List(["2025-08-13", "2025-08-14", "2025-08-15", "2025-08-16"])
result = ee.FeatureCollection(days.map(daily)).getInfo()
for feature in result["features"]:
    print(feature["properties"])
print(f"took {time.time() - started:.1f} s")
