"""
Monthly VC processing module
"""

import ee
import os
import time
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Any
from .core import VCProcessor
from .utils import create_output_directory, export_with_geedim, maskS2clouds, addNDVI

def month_VCpy(
    service_account_email: str = None,
    service_account_key_file: str = None,
    output_path: str = None,
    year: int = 2025,
    start_month: int = 1,
    end_month: int = 12,
    ndvi_threshold: float = 0.15,
    cloud_cover_max: int = 15,
    max_workers: int = 4,
    export_ndvi: bool = False,  # NEW PARAMETER
    metro_asset: str = None,
    aoi_asset: str = None,
    crs: str = 'EPSG:32638',
    scale: int = 10,
    dtype: str = 'float32'
):
    """
    Run monthly vegetation cover analysis
    
    Args:
        service_account_email: GEE service account email
        service_account_key_file: Path to service account key file
        output_path: Output directory path
        year: Year to process
        start_month: Starting month (1-12)
        end_month: Ending month (1-12)
        ndvi_threshold: NDVI threshold for vegetation cover
        cloud_cover_max: Maximum cloud cover percentage
        max_workers: Number of parallel workers
        export_ndvi: Whether to export NDVI images in addition to VC
        metro_asset: Asset path for metro region
        aoi_asset: Asset path for AOI region
        crs: Coordinate reference system
        scale: Pixel scale in meters
        dtype: Data type for export
        
    Returns:
        Dict with processing results
    """
    from .config import DEFAULT_CONFIG
    from .utils import initialize_earth_engine, suppress_warnings
    
    # Suppress warnings
    suppress_warnings()
    
    # Prepare configuration
    config = DEFAULT_CONFIG.copy()
    
    # Override with provided arguments
    if service_account_email:
        config['service_account_email'] = service_account_email
    if service_account_key_file:
        config['service_account_key_file'] = service_account_key_file
    if output_path:
        config['output_base_path'] = output_path
    else:
        config['output_base_path'] = r"D:\Gergo\GEEpy\output"
    
    if metro_asset:
        config['metro_asset'] = metro_asset
    if aoi_asset:
        config['aoi_asset'] = aoi_asset
    
    config.update({
        'year': year,
        'start_month': start_month,
        'end_month': end_month,
        'ndvi_threshold': ndvi_threshold,
        'cloud_cover_max': cloud_cover_max,
        'max_workers': max_workers,
        'export_ndvi': export_ndvi,  # Store in config
        'crs': crs,
        'scale': scale,
        'dtype': dtype,
        'output_path': os.path.join(config['output_base_path'], 'monthly')
    })
    
    # Initialize Earth Engine
    if not initialize_earth_engine(config):
        return {'success': False, 'error': 'Earth Engine initialization failed'}
    
    # Create processor and run
    processor = MonthlyProcessor(config)
    return processor.run()


class MonthlyProcessor(VCProcessor):
    """Processor for monthly VC analysis"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if 'aoi_asset' in config:
            self.aoi = ee.FeatureCollection(config['aoi_asset'])
        else:
            self.aoi = self.metro
        
        # Initialize cloud mask and NDVI functions
        self.maskS2clouds = maskS2clouds
        self.addNDVI = lambda img: addNDVI(img, self.config['ndvi_threshold'])
        self.export_with_geedim = lambda img, filename: export_with_geedim(
            img, filename, self.region, self.config
        )
    
    def create_monthly_periods(self) -> List[Dict[str, Any]]:
        """Create monthly periods for processing"""
        periods = []
        for month in range(self.config['start_month'], self.config['end_month'] + 1):
            start_date = ee.Date.fromYMD(self.config['year'], month, 1)
            end_date = start_date.advance(1, 'month')
            label = start_date.format('YYYY-MM').getInfo()
            periods.append({
                'month': month,
                'start': start_date,
                'end': end_date,
                'label': label
            })
        
        print(f"📅 Processing {len(periods)} months ({self.config['start_month']} to {self.config['end_month']})")
        print(f'📊 NDVI Export: {"ENABLED" if self.config["export_ndvi"] else "DISABLED (VC only)"}')
        return periods
    
    def process_month(self, month_info: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single month - now returns both VC and NDVI if enabled"""
        month_num = month_info['month']
        label = month_info['label']
        start = month_info['start']
        end = month_info['end']
        
        print(f"  Processing {label}...", end='')
        start_time = time.time()
        
        # Get image collection
        ic = ee.ImageCollection('COPERNICUS/S2_HARMONIZED') \
            .filterDate(start, end) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', self.config['cloud_cover_max'])) \
            .filterBounds(self.metro) \
            .select(['B4', 'B8', 'QA60'])
        
        image_count = ic.size().getInfo()
        
        # Extract source image names
        source_images = []
        if image_count > 0:
            try:
                source_list = ic.limit(100).aggregate_array('system:index').getInfo()
                for img_name in source_list:
                    if isinstance(img_name, str):
                        parts = img_name.split('/')
                        source_images.append(parts[-1] if len(parts) >= 3 else img_name)
            except:
                pass
        
        if image_count == 0:
            elapsed = time.time() - start_time
            print(f" ⚠️ No images found ({elapsed:.1f}s)")
            result = {
                'month': month_num,
                'label': label,
                'vc_mosaic': ee.Image.constant(0).rename('vc').clip(self.metro).rename(label),
                'image_count': 0,
                'coverage_percent': 0,
                'source_images': source_images,
                'success': True
            }
            
            if self.config['export_ndvi']:
                result['ndvi_mosaic'] = ee.Image.constant(-9999).rename('ndvi').clip(self.metro).rename(label)
            
            return result
        
        # Process collection
        processed_ic = ic.map(self.maskS2clouds).map(self.addNDVI)
        
        # Create VC mosaic
        vc_mosaic = processed_ic.select('vc').mosaic().rename(label).clip(self.metro)
        
        # Create NDVI mosaic if enabled
        if self.config['export_ndvi']:
            ndvi_mosaic = processed_ic.select('ndvi').mean() \
                .unmask(-9999) \
                .clip(self.metro) \
                .rename(label)
        
        # Calculate coverage percentage
        try:
            coverage = vc_mosaic.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=self.aoi.geometry(),
                scale=10,
                maxPixels=1e13
            ).get(label)
            
            coverage_val = coverage.getInfo() if coverage else 0
            coverage_percent = coverage_val * 100
        except Exception as e:
            print(f"Warning: Coverage calculation failed for {label}: {str(e)}")
            coverage_percent = 0
        
        # Create metadata
        metadata = {
            'Year': self.config['year'],
            'Month': label,
            'DataType': 'VC',
            'ImageCount': image_count,
            'CoveragePercent': coverage_percent,
            'VC_Filename': f'VC_{label}_thr_{str(self.config["ndvi_threshold"]).replace(".", "_")}',
            'Threshold': self.config['ndvi_threshold'],
            'CloudCoverMax': self.config['cloud_cover_max'],
            'Source_Images': ', '.join(source_images[:10]) + ('...' if len(source_images) > 10 else ''),
            'Processing_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Create NDVI metadata if needed
        if self.config['export_ndvi']:
            ndvi_metadata = metadata.copy()
            ndvi_metadata['Data_Type'] = 'NDVI_mean'
            ndvi_metadata['NDVI_Filename'] = f'NDVI_{label}_thr_{str(self.config["ndvi_threshold"]).replace(".", "_")}'
        
        elapsed = time.time() - start_time
        print(f" ✅ {image_count} images, {coverage_percent:.1f}% VC ({elapsed:.1f}s)")
        
        result = {
            'month': month_num,
            'label': label,
            'vc_mosaic': vc_mosaic,
            'image_count': image_count,
            'coverage_percent': coverage_percent,
            'source_images': source_images,
            'metadata': metadata,
            'success': True
        }
        
        if self.config['export_ndvi']:
            result['ndvi_mosaic'] = ndvi_mosaic
            result['ndvi_metadata'] = ndvi_metadata
        
        return result
    
    def create_annual_composite(self, results: List[Dict]) -> tuple:
        """Create annual composites from monthly mosaics - now returns both VC and NDVI if enabled"""
        print(f"\n🎯 Creating annual composite...")
        start_time = time.time()
        
        vc_mosaics = []
        ndvi_mosaics = []
        labels = []
        
        for result in results:
            if 'vc_mosaic' in result:
                vc_mosaics.append(result['vc_mosaic'])
                labels.append(result['label'])
                if self.config['export_ndvi'] and 'ndvi_mosaic' in result:
                    ndvi_mosaics.append(result['ndvi_mosaic'])
        
        if not vc_mosaics:
            print("  ❌ No monthly mosaics available")
            return None, None
        
        # Create VC composite
        vc_ic = ee.ImageCollection.fromImages(vc_mosaics)
        annual_vc = vc_ic.toBands() \
            .rename(labels) \
            .clip(self.metro) \
            .set({
                'year': self.config['year'],
                'threshold': self.config['ndvi_threshold'],
                'cloud_filter': self.config['cloud_cover_max'],
                'creation_date': datetime.now().strftime('%Y-%m-%d'),
                'description': f'Monthly VC composite {self.config["start_month"]:02d}-{self.config["end_month"]:02d} {self.config["year"]}'
            })
        
        # Create NDVI composite if enabled
        annual_ndvi = None
        if self.config['export_ndvi'] and ndvi_mosaics:
            ndvi_ic = ee.ImageCollection.fromImages(ndvi_mosaics)
            annual_ndvi = ndvi_ic.toBands() \
                .rename(labels) \
                .clip(self.metro) \
                .set({
                    'year': self.config['year'],
                    'threshold': self.config['ndvi_threshold'],
                    'cloud_filter': self.config['cloud_cover_max'],
                    'creation_date': datetime.now().strftime('%Y-%m-%d'),
                    'description': f'Monthly NDVI composite {self.config["start_month"]:02d}-{self.config["end_month"]:02d} {self.config["year"]}'
                })
        
        elapsed = time.time() - start_time
        print(f"  ✅ Annual composite created ({elapsed:.1f}s)")
        print(f"  📊 Contains {len(vc_mosaics)} monthly bands")
        
        return annual_vc, annual_ndvi
    
    def export_annual_composites(self, annual_vc: ee.Image, annual_ndvi: ee.Image) -> tuple:
        """Export annual composites to TIFF - now exports both VC and NDVI if enabled"""
        vc_success = False
        ndvi_success = False
        
        # Export VC composite
        if annual_vc is not None:
            vc_filename = f'VC_Annual_{self.config["year"]}_thr_{str(self.config["ndvi_threshold"]).replace(".", "_")}'
            vc_filename += f'_{self.config["start_month"]:02d}_{self.config["end_month"]:02d}.tif'
            
            print(f"\n📤 Exporting VC annual composite...")
            print(f"  Filename: {vc_filename}")
            print(f"  Note: This may take several minutes (contains {self.config["end_month"] - self.config["start_month"] + 1} bands)")
            
            vc_success = self.export_with_geedim(annual_vc, vc_filename)
        
        # Export NDVI composite if enabled
        if self.config['export_ndvi'] and annual_ndvi is not None:
            ndvi_filename = f'NDVI_Annual_{self.config["year"]}_thr_{str(self.config["ndvi_threshold"]).replace(".", "_")}'
            ndvi_filename += f'_{self.config["start_month"]:02d}_{self.config["end_month"]:02d}.tif'
            
            print(f"\n📤 Exporting NDVI annual composite...")
            print(f"  Filename: {ndvi_filename}")
            
            ndvi_success = self.export_with_geedim(annual_ndvi, ndvi_filename)
        
        return vc_success, ndvi_success
    
    def run(self) -> Dict[str, Any]:
        """Run monthly processing pipeline - now supports NDVI export"""
        total_start_time = time.time()
        
        print("\n" + "=" * 70)
        print("🚀 MONTHLY VC PROCESSING")
        if self.config['export_ndvi']:
            print("📊 MODE: VC + NDVI Export")
        else:
            print("📊 MODE: VC Only")
        print("=" * 70)
        
        # Step 1: Create output directory
        if not create_output_directory(self.config['output_path']):
            return {'success': False, 'error': 'Failed to create output directory'}
        
        # Step 2: Create monthly periods
        month_infos = self.create_monthly_periods()
        
        # Step 3: Process all months
        results = self.process_all_months(month_infos)
        
        # Step 4: Export metadata
        metadata_filename = f"{self.config['year']}_Monthly_VC"
        if self.config['export_ndvi']:
            metadata_filename += "_NDVI"
        metadata_filename += "_Metadata.csv"
        
        # Collect all metadata
        all_metadata = []
        for result in results:
            if 'metadata' in result:
                all_metadata.append(result['metadata'])
                if self.config['export_ndvi'] and 'ndvi_metadata' in result:
                    all_metadata.append(result['ndvi_metadata'])
        
        metadata_success = False
        if all_metadata:
            metadata_success = self.export_metadata(all_metadata, metadata_filename)
        
        # Step 5: Create and export annual composites
        annual_vc, annual_ndvi = self.create_annual_composite(results)
        vc_success, ndvi_success = self.export_annual_composites(annual_vc, annual_ndvi)
        
        # Step 6: Generate summary
        total_time = time.time() - total_start_time
        
        print("\n" + "=" * 70)
        print("📊 FINAL SUMMARY")
        print("=" * 70)
        print(f"Total processing time: {total_time:.1f} seconds")
        print(f"Metadata export: {'✅ SUCCESS' if metadata_success else '❌ FAILED'}")
        print(f"VC composite export: {'✅ SUCCESS' if vc_success else '❌ FAILED'}")
        if self.config['export_ndvi']:
            print(f"NDVI composite export: {'✅ SUCCESS' if ndvi_success else '❌ FAILED'}")
        
        # List generated files
        if os.path.exists(self.config['output_path']):
            files = os.listdir(self.config['output_path'])
            tif_files = [f for f in files if f.endswith('.tif')]
            csv_files = [f for f in files if f.endswith('.csv')]
            
            if tif_files or csv_files:
                print(f"\n📁 Generated files in {self.config['output_path']}:")
                
                if tif_files:
                    print(f"  Image files ({len(tif_files)}):")
                    for file in sorted(tif_files):
                        file_path = os.path.join(self.config['output_path'], file)
                        file_size = os.path.getsize(file_path) / (1024 * 1024)
                        print(f"    • {file} ({file_size:.1f} MB)")
                
                if csv_files:
                    print(f"  Metadata files ({len(csv_files)}):")
                    for file in sorted(csv_files):
                        file_path = os.path.join(self.config['output_path'], file)
                        file_size = os.path.getsize(file_path) / 1024
                        print(f"    • {file} ({file_size:.1f} KB)")
            else:
                print("\n⚠️ No files were generated")
        
        # Determine overall success
        success = metadata_success and vc_success
        if self.config['export_ndvi']:
            success = success and ndvi_success
        
        return {
            'success': success,
            'processing_time': total_time,
            'metadata_export': metadata_success,
            'vc_composite_export': vc_success,
            'ndvi_composite_export': ndvi_success if self.config['export_ndvi'] else None,
            'months_processed': len(results),
            'months_with_data': sum(1 for r in results if r['image_count'] > 0),
            'total_source_images': sum(r['image_count'] for r in results),
            'output_path': self.config['output_path']
        }