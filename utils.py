"""
Utility functions for VCpy
"""

import ee
import os
import time
import warnings
from typing import Dict, Any
import geedim

def initialize_earth_engine(config: Dict[str, Any]) -> bool:
    """
    Initialize Earth Engine with service account credentials
    
    Args:
        config: Configuration dictionary
        
    Returns:
        bool: True if successful
    """
    print("=" * 70)
    print("🌱 INITIALIZING EARTH ENGINE")
    print("=" * 70)
    
    try:
        credentials = ee.ServiceAccountCredentials(
            config['service_account_email'],
            config['service_account_key_file']
        )
        ee.Initialize(credentials)
        # geedim will use the already initialized Earth Engine session
        print(f"✅ Initialized with service account: {config['service_account_email']}")
        print(f"✅ Earth Engine ready")
        return True
    except Exception as e:
        print(f"❌ Earth Engine initialization failed: {str(e)}")
        return False

def export_with_geedim(image, filename: str, region, config: Dict[str, Any]) -> bool:
    """
    Export image using geedim
    
    Args:
        image: Earth Engine image to export
        filename: Output filename
        region: Region geometry
        config: Configuration dictionary
        
    Returns:
        bool: True if successful
    """
    full_path = os.path.join(config['output_path'], filename)
    
    # If file already exists, remove it or handle it gracefully
    if os.path.exists(full_path):
        print(f"  ⚠️ File {filename} already exists, overwriting...")
        try:
            os.remove(full_path)
        except:
            # If we can't remove it, return True since file exists
            file_size = os.path.getsize(full_path) / (1024 * 1024)
            print(f'  ✅ File already exists: {filename} ({file_size:.1f} MB)')
            return True
    
    try:
        # Convert the region to GeoJSON-like dictionary
        region_geojson = region.getInfo()
        
        # Create a MaskedImage object first
        gd_image = geedim.MaskedImage(image)
        
        # Then download it
        gd_image.download(
            full_path,
            region=region_geojson,
            scale=config['scale'],
            crs=config['crs'],
            dtype=config['dtype']
        )
        
        if os.path.exists(full_path):
            file_size = os.path.getsize(full_path) / (1024 * 1024)
            print(f'  ✅ Exported: {filename} ({file_size:.1f} MB)')
            return True
        else:
            print(f'  ❌ File not created: {filename}')
            return False
            
    except Exception as e:
        # If the error is about file existing, and the file actually exists, consider it a success
        if "exists" in str(e).lower() and os.path.exists(full_path):
            file_size = os.path.getsize(full_path) / (1024 * 1024)
            print(f'  ✅ File already exists: {filename} ({file_size:.1f} MB)')
            return True
        else:
            print(f'  ❌ Export failed for {filename}: {str(e)}')
            return False
            
def maskS2clouds(image):
    """Cloud masking for Sentinel-2"""
    qa = image.select('QA60')
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(
        qa.bitwiseAnd(cirrusBitMask).eq(0))
    return image.updateMask(mask).divide(10000)

def addNDVI(image, ndvi_threshold: float):
    """Calculate NDVI and vegetation cover"""
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('ndvi')
    vc = ndvi.gte(ndvi_threshold).rename('vc')
    return image.addBands([ndvi, vc])

def create_output_directory(output_path: str) -> bool:
    """
    Create output directory if it doesn't exist
    
    Args:
        output_path: Path to output directory
        
    Returns:
        bool: True if directory exists or was created
    """
    if not os.path.exists(output_path):
        try:
            os.makedirs(output_path)
            print(f"📁 Created output directory: {output_path}")
            return True
        except Exception as e:
            print(f"❌ Failed to create output directory: {str(e)}")
            return False
    return True

def suppress_warnings():
    """Suppress unnecessary warnings"""
    warnings.filterwarnings('ignore', message="Couldn't find STAC entry for: 'None'")