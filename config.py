"""
Configuration and default settings for VCpy
"""

import os
from typing import Dict, Any

# Default configuration
DEFAULT_CONFIG = {
    # Authentication
    'service_account_email': "yourproject-mailer@ee-your.iam.gserviceaccount.com",
    'service_account_key_file': r"path\to\ee-your-yournumber.json",

    # Output path
    'output_base_path': r"D:\Gergo\GEEpy\output",
    
    # Processing parameters (bi-weekly defaults)
    'year': 2025,
    'months': 12,      # For bi-weekly: total months to process
    'start_month': 1,  # For monthly: starting month
    'end_month': 12,   # For monthly: ending month
    'ndvi_threshold': 0.15,
    'cloud_cover_max': 15,
    'acquisition_window': 21,  # For bi-weekly
    'max_workers': 4,
    
    # Export control - replaced export_ndvi with output_mode
    'output_mode': 'vc',  # 'vc', 'ndvi', or 'both'
    
    # Spatial assets
    'metro_asset': "projects/ee-dijogergo/assets/METRO",
    'aoi_asset': "projects/ee-dijogergo/assets/Metropol_R",
    
    # Export parameters
    'crs': 'EPSG:32638',
    'scale': 10,
    'dtype': 'float32'
}

def validate_config(config: Dict[str, Any]) -> bool:
    """Validate configuration parameters"""
    # Check required paths exist
    if not os.path.exists(config['service_account_key_file']):
        raise FileNotFoundError(f"Service account key file not found: {config['service_account_key_file']}")
    
    # Validate parameters
    if not 1 <= config['months'] <= 12:
        raise ValueError("Months must be between 1 and 12")
    
    if not 0 <= config['ndvi_threshold'] <= 1:
        raise ValueError("NDVI threshold must be between 0 and 1")
    
    if not 0 <= config['cloud_cover_max'] <= 100:
        raise ValueError("Cloud cover must be between 0 and 100")
    
    if config.get('output_mode') not in ['vc', 'ndvi', 'both']:
        raise ValueError("output_mode must be 'vc', 'ndvi', or 'both'")
    
    return True