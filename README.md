# VCpy

[![Lifecycle: experimental](https://img.shields.io/badge/lifecycle-experimental-orange.svg)](https://lifecycle.r-lib.org/articles/stages.html#experimental)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A powerful Python package for Vegetation Cover analysis using Google Earth Engine and Sentinel-2 imagery. VCpy provides both bi-weekly and monthly vegetation cover data acquisition with parallel processing capabilities.

## Features

- 📅 **Bi-weekly analysis**: Process vegetation cover data in 15-day intervals with configurable acquisition windows
- 📅 **Monthly analysis**: Generate monthly vegetation cover composites
- 📊 **Flexible output modes**: Export VC only, NDVI only, or both simultaneously
- ⚡ **Parallel processing**: Utilize multiple workers for faster data acquisition
- 📈 **Metadata export**: Automatically export CSV metadata with source image information
- 🌐 **Google Earth Engine integration**: Built on top of the official Earth Engine API
- ☁️ **Cloud masking**: Built-in cloud masking for Sentinel-2 imagery
- 🔧 **Configurable parameters**: Customize NDVI thresholds, cloud cover limits, acquisition windows, and more
- 🎯 **Month range selection**: Process any month range (e.g., growing season only)

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

# Bi-weekly: NDVI only for January-June
biweek_VCpy(
    year=2025,
    start_month=1,
    end_month=6,
    output_mode='ndvi'
)

# Monthly: Both VC and NDVI for full year
month_VCpy(
    year=2025,
    output_mode='both',
    ndvi_threshold=0.15,
    cloud_cover_max=15
)

# Monthly: VC only for growing season (April-September)
month_VCpy(
    year=2024,
    start_month=4,
    end_month=9,
    output_mode='vc',
    output_path="path/to/output"
)
```
### Command Line Interface
```bash
# Monthly: NDVI only for January-June
python -m VCpy.cli monthly --year 2025 --output-mode ndvi --start-month 1 --end-month 6

# Monthly: Both VC and NDVI for full year
python -m VCpy.cli monthly --year 2025 --output-mode both --start-month 1 --end-month 12

# Bi-weekly: VC only for summer months with custom settings
python -m VCpy.cli biweekly \
    --year 2024 \
    --output-mode vc \
    --start-month 6 \
    --end-month 9 \
    --acquisition-window 30 \
    --cloud-cover-max 20

# Bi-weekly: NDVI only for January-June
python -m VCpy.cli biweekly \
    --year 2025 \
    --output-mode ndvi \
    --start-month 1 \
    --end-month 6 \
    --output-path "path/to/output"

# Monthly with custom geometry
python -m VCpy.cli monthly \
    --year 2024 \
    --output-mode both \
    --start-month 3 \
    --end-month 9 \
    --metro-asset "projects/yourproject/assets/custom-region"
```
## Parameters

| Parameter | Description | Monthly Default | Bi-weekly Default |
|-----------|-------------|-----------------|-------------------|
| `--year` | Year to process | 2025 | 2025 |
| `--start-month` | Starting month (1-12) | 1 | 1 |
| `--end-month` | Ending month (1-12) | 12 | 12 |
| `--output-mode` | `vc`, `ndvi`, or `both` | `vc` | `vc` |
| `--output-path` | Custom output directory | `path\to\output` | `path\to\output` |
| `--ndvi-threshold` | NDVI threshold for vegetation | 0.15 | 0.15 |
| `--cloud-cover-max` | Maximum cloud cover % | 15 | 40 |
| `--acquisition-window` | Days to search for images | N/A | 21 |
| `--max-workers` | Parallel threads | 4 | 4 |
| `--metro-asset` | GEE asset for region | From config | From config |
| `--aoi-asset` | GEE asset for AOI (optional) | From config | N/A |
| `--crs` | Coordinate reference system | EPSG:32638 | EPSG:32638 |
| `--scale` | Pixel scale in meters | 10 | 10 |
| `--dtype` | Data type for export | float32 | float32 |

## Configuration

### Default Settings

The package comes with sensible defaults defined in `config.py`. **You MUST update these with your own credentials and assets:**

```python
# Authentication - UPDATE THESE!
service_account_email = "your-service-account@your-project.iam.gserviceaccount.com"
service_account_key_file = r"path/to/your-service-account-key.json"

# Output directory - UPDATE THIS!
output_base_path = r"C:\Users\YourName\GEEpy\output"

# Processing parameters (adjust as needed)
output_mode = 'vc'  # 'vc', 'ndvi', or 'both'
ndvi_threshold = 0.15
cloud_cover_max = 40  # Bi-weekly: 40%, Monthly: 15%
acquisition_window = 21  # Bi-weekly only
max_workers = 4

# GEE Assets - UPDATE THESE!
metro_asset = "projects/your-project/assets/METRO"
aoi_asset = "projects/your-project/assets/AOI"  # Optional

# Export parameters
crs = 'EPSG:32638'
scale = 10
dtype = 'float32'
```
⚠️ Important: You must replace the placeholder values (everything in quotes) with your actual Google Earth Engine credentials and asset paths before running. See the Google Earth Engine documentation for help setting up service accounts.

### Override Settings

You can overwrite any parameter directly when calling functions:
```python
biweek_VCpy(
    output_mode='ndvi',
    start_month=1,
    end_month=6,
    cloud_cover_max=20
)
```
## Output Files

### Monthly Mode

Generates a single multi-band TIFF file:
```text
output/monthly/
├── VC_Annual_2025_thr_0_15_01_12.tif      # Multi-band VC composite (one band per month)
├── NDVI_Annual_2025_thr_0_15_01_12.tif    # Multi-band NDVI composite (if output_mode='ndvi' or 'both')
└── 2025_Monthly_VC_NDVI_01_12_Metadata.csv
```
### Bi-weekly Mode

Generates 2-band TIFF files for each 2-month period: 
```text
output/biweekly/
├── 2025_BiWeekly_VC_01_02.tif      # January 1-15 + January 16-31
├── 2025_BiWeekly_VC_03_04.tif      # February 1-15 + February 16-28/29
├── 2025_BiWeekly_VC_05_06.tif      # March 1-15 + March 16-31
├── ... (continues for all months)
├── 2025_BiWeekly_NDVI_01_02.tif    # Only if output_mode='ndvi' or 'both'
├── 2025_BiWeekly_NDVI_03_04.tif    # Only if output_mode='ndvi' or 'both'
└── 2025_BiWeekly_VC_NDVI_01_06_Metadata.csv
```
### Metadata Contents

Both modes generate CSV metadata containing:

- Source image names and counts
- Processing dates and parameters
- Quality flags and coverage statistics
- Acquisition windows and cloud cover information
- Data type (VC or NDVI)

## Examples

### Example 1: Quick analysis (default parameters)
```python
import ee
from VCpy import biweek_VCpy, month_VCpy

# Analyze 2024 data (VC only, full year)
biweek_VCpy(year=2024)
month_VCpy(year=2024)
```
### Example 2:Growing Season Analysis (April-September)
```python
# Analyze growing season (April-September)
month_VCpy(
    year=2024,
    start_month=4,
    end_month=9,
    ndvi_threshold=0.2,
    cloud_cover_max=20,
    output_mode='both'        # Get both VC and NDVI
)
```
### Example 3: NDVI-only Bi-weekly Analysis
```python
# Get NDVI only for January-June with custom acquisition window
biweek_VCpy(
    year=2025,
    start_month=1,
    end_month=6,
    output_mode='ndvi',
    acquisition_window=30,  # 30-day window for cloudier months
    cloud_cover_max=30
)
```
### Example 4: Custom Geometry
```python
# Process with custom region
biweek_VCpy(
    year=2025,
    start_month=1,
    end_month=6,
    metro_asset="projects/yourproject/assets/custom-region",
    output_mode='vc'
)
```

### Example 5: Batch Processing Multiple Years
```python
for year in [2020, 2021, 2022, 2023, 2024]:
    print(f"Processing {year}...")
    biweek_VCpy(
        year=year,
        start_month=1,
        end_month=12,
        output_mode='both',
        output_path=f"./output/{year}"
    )
```

### Example 6: Command Line 
```bash
# Process June-August (summer months) with NDVI only
python -m VCpy.cli monthly \
    --year 2024 \
    --output-mode ndvi \
    --start-month 6 \
    --end-month 8 \
    --cloud-cover-max 35

# Bi-weekly with 25-day acquisition window for cloudy season
python -m VCpy.cli biweekly \
    --year 2024 \
    --output-mode both \
    --start-month 1 \
    --end-month 3 \
    --acquisition-window 25
```
## Understanding Bi-weekly Periods

The bi-weekly mode uses overlapping acquisition windows to ensure sufficient cloud-free imagery:
```text
Period 1 (Jan 01):  [Dec 11 ─────────── Jan 01]  (21-day window)
Period 2 (Jan 16):        [Dec 26 ─────────── Jan 16]
Period 3 (Jan 31):              [Jan 10 ─────────── Jan 31]
```
Why overlapping windows?
- Data availability: More images per period (22-55 images typical)
- Cloud resilience: Multiple chances to get cloud-free imagery
- Smooth transitions: Overlapping windows create smoother time series

Adjusting the window:
- `--acquisition-window` 14: For cloud-free regions (deserts, arid climates)
- `--acquisition-window` 21: Default - works for most regions
- `--acquisition-window` 30: For cloudy regions (tropical, winter months)

## License

MIT License - see `LICENSE` file for details
