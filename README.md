# VCpy

[![Lifecycle: experimental](https://img.shields.io/badge/lifecycle-experimental-orange.svg)](https://lifecycle.r-lib.org/articles/stages.html#experimental)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A powerful Python package for Vegetation Cover analysis using Google Earth Engine and Sentinel-2 imagery. VCpy provides both bi-weekly and monthly vegetation cover data acquisition with parallel processing capabilities.

## Features

- 📅 Bi-weekly VC analysis: Process vegetation cover data in 15-day intervals
- 📅 Monthly VC analysis: Generate monthly vegetation cover composites
- ⚡ Parallel processing: Utilize multiple workers for faster data acquisition
- 📊 Metadata export: Automatically export CSV metadata with source image information
- 🌐 Google Earth Engine integration: Built on top of the official Earth Engine API
- ☁️ Cloud masking: Built-in cloud masking for Sentinel-2 imagery
- 🔧 Configurable parameters: Customize NDVI thresholds, cloud cover limits, and more

## Installation
```bash
# Clone the repository
git clone https://github.com/DijoG/VCpy.git
cd VCpy

# Install in development mode
pip install -e .
```
### Dependencies

The package automatically installs:

- earthengine-api (Google Earth Engine Python API)
- geedim (Enhanced Earth Engine image download capabilities)

## Quick Start

### Python API
```python
from VCpy import biweek_VCpy, month_VCpy

# Run bi-weekly analysis with default parameters
biweek_VCpy(year=2025, months=6)

# Run monthly analysis with custom parameters
month_VCpy(
    year=2025,
    start_month=1,
    end_month=12,
    ndvi_threshold=0.15,
    cloud_cover_max=15,
    output_path="path/to/output"
)
```
### Command Line Interface

after installation, you can use CLI commands:
```bash
# Bi-weekly analysis
vcpy-biweekly --year 2025 --months 12

# Monthly analysis
vcpy-monthly --year 2025 --start-month 1 --end-month 12

# With custom parameters
vcpy-biweekly --year 2024 --months 6 --ndvi-threshold 0.2 --cloud-cover-max 20
vcpy-monthly --year 2024 --start-month 3 --end-month 9 --export-ndvi --output-path ./vc_output
```

## Configuration

### Default Settings

The package comes with sensible defaults for your setup:
```python
# Authentication
service_account_email = "vegcov-mailer@yourproject.iam.gserviceaccount.com"
service_account_key_file = r"D:\Gergo\GEEpy\json\yourproject-yourauthkey.json"

# Output paths
output_base_path = r"D:\Gergo\GEEpy\output"

# Processing parameters
ndvi_threshold = 0.15
cloud_cover_max = 40  # Bi-weekly: 40%, Monthly: 15%
acquisition_window = 21  # Bi-weekly only
max_workers = 4

# Spatial assets
metro_asset = "projects/yourproject/assets/METRO"  # A simplified geometry of aoi_asset (geometry)
aoi_asset = "projects/yourproject/assets/Metropol" # Define ONLY if Vegatation Coverage percentage 
                                                   # calculation should use a different geometry from 
                                                   # metro_asset. Otherwise, it automatically uses 
                                                   # metro_asset. 

# Export parameters
export_ndvi = False
crs = 'EPSG:32638'
scale = 10
dtype = 'float32'
```
### Custom Configuration

You can overwrite any default parameter when calling the functions:
```python
# Full customization example
biweek_VCpy(
    service_account_email="your-email@yourproject.iam.gserviceaccount.com",
    service_account_key_file="/path/to/yourcredentials.json",
    output_path="/custom/output/path",
    year=2025,
    months=12,
    ndvi_threshold=0.18,
    cloud_cover_max=30,
    acquisition_window=21,
    max_workers=8,
    export_ndvi=True,
    metro_asset="projects/yourproject/assets/your-region",
    crs='EPSG:4326',
    scale=20
)
```
## Output Files

### Bi-weekly Mode

Generates 2-band TIFF files for each 2-month period: 
```text
output/biweekly/
├── 2025_BiWeekly_VC_01_02.tif      # January 1-15 + January 16-31
├── 2025_BiWeekly_VC_03_04.tif      # February 1-15 + February 16-28/29
├── 2025_BiWeekly_VC_05_06.tif      # March 1-15 + March 16-31
├── ... (continues for all months)
├── 2025_BiWeekly_NDVI_01_02.tif    # Only if export_ndvi=True
├── 2025_BiWeekly_NDVI_03_04.tif    # Only if export_ndvi=True
└── 2025_BiWeekly_VC_NDVI_Metadata.csv
```

### Monthly Mode

Generates a single multi-band TIFF file:
```text
output/monthly/
├── VC_Annual_2025_thr_0_15_01_12.tif      # 12-band VC composite (one band per month)
├── NDVI_Annual_2025_thr_0_15_01_12.tif    # 12-band NDVI composite (if export_ndvi=True)
└── 2025_Monthly_VC_NDVI_Metadata.csv      # Combined metadata
```

### Metadata Files

Both modes generate CSV metadata containing:

- Source image names and counts
- Processing dates and parameters
- Quality flags and coverage statistics
- Acquisition windows and cloud cover information

## Examples

### Example 1: Quick analysis
```python
import ee
from VCpy import biweek_VCpy
# Analyze 2024 data
biweek_VCpy(year=2024)
month_VCpy(year=2024)
```
### Example 2: Custom Season Analysis
```python
# Analyze growing season (April-September)
month_VCpy(
    year=2024,
    start_month=4,
    end_month=9,
    ndvi_threshold=0.2,
    cloud_cover_max=20,
    export_ndvi=True        # Gives you NDVI besides VC too!
)
```
### Example 3: Custom Geometry
```python
# Initialize with custom region
biweek_VCpy(
    year=2025,
    months=6,               # January-June
    metro_asset="projects/yourproject/assets/custom-region"
)
```
### Example 4: Batch Processing Multiple Years
```python
for year in [2020, 2021, 2022, 2023, 2024]:
    print(f"Processing {year}...")
    biweek_VCpy(
        year=year,
        months=12,
        output_path=f"./output/{year}"
    )
```
