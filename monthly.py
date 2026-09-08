"""
Monthly VC processing module
"""

import ee
import os
import time
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Any, Optional
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
    output_mode: str = 'vc',  # 'vc', 'ndvi', or 'both'
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
        output_mode: Output type - 'vc' (VC only), 'ndvi' (NDVI only), or 'both' (VC + NDVI)
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
        'output_mode': output_mode,
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
        
        output_mode = self.config['output_mode']
        mode_labels = {
            'vc': 'VC Only',
            'ndvi': 'NDVI Only',
            'both': 'VC + NDVI'
        }
        print(f'📊 Output Mode: {mode_labels.get(output_mode, "VC Only")}')
        return periods
    
    def process_month(self, month_info: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single month - creates VC, NDVI, or both based on output_mode"""
        month_num = month_info['month']
        label = month_info['label']
        start = month_info['start']
        end = month_info['end']
        output_mode = self.config['output_mode']
        
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
                'image_count': 0,
                'coverage_percent': 0,
                'source_images': source_images,
                'success': True
            }
            
            # Add appropriate placeholders based on mode
            if output_mode in ['vc', 'both']:
                result['vc_mosaic'] = ee.Image.constant(0).rename('vc').clip(self.metro).rename(label)
            if output_mode in ['ndvi', 'both']:
                result['ndvi_mosaic'] = ee.Image.constant(-9999).rename('ndvi').clip(self.metro).rename(label)
            
            return result
        
        # Process collection
        processed_ic = ic.map(self.maskS2clouds).map(self.addNDVI)
        
        result = {
            'month': month_num,
            'label': label,
            'image_count': image_count,
            'source_images': source_images,
            'success': True
        }
        
        # Create VC mosaic if needed
        if output_mode in ['vc', 'both']:
            vc_mosaic = processed_ic.select('vc').mosaic().rename(label).clip(self.metro)
            result['vc_mosaic'] = vc_mosaic
            
            # Calculate coverage percentage
            try:
                coverage = vc_mosaic.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=self.aoi.geometry(),
                    scale=10,
                    maxPixels=1e13
                ).get(label)
                
                coverage_val = coverage.getInfo() if coverage else 0
                result['coverage_percent'] = coverage_val * 100
            except Exception as e:
                print(f"Warning: Coverage calculation failed for {label}: {str(e)}")
                result['coverage_percent'] = 0
            
            # VC metadata
            result['metadata'] = {
                'Year': self.config['year'],
                'Month': label,
                'DataType': 'VC',
                'ImageCount': image_count,
                'CoveragePercent': result['coverage_percent'],
                'VC_Filename': f'VC_{label}_thr_{str(self.config["ndvi_threshold"]).replace(".", "_")}',
                'Threshold': self.config['ndvi_threshold'],
                'CloudCoverMax': self.config['cloud_cover_max'],
                'Source_Images': ', '.join(source_images[:10]) + ('...' if len(source_images) > 10 else ''),
                'Processing_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        # Create NDVI mosaic if needed
        if output_mode in ['ndvi', 'both']:
            ndvi_mosaic = processed_ic.select('ndvi').max() \
                .unmask(-9999) \
                .clip(self.metro) \
                .rename(label)
            result['ndvi_mosaic'] = ndvi_mosaic
            
            # NDVI metadata
            ndvi_metadata = {
                'Year': self.config['year'],
                'Month': label,
                'DataType': 'NDVI_max',
                'ImageCount': image_count,
                'NDVI_Filename': f'NDVI_{label}_thr_{str(self.config["ndvi_threshold"]).replace(".", "_")}',
                'Threshold': self.config['ndvi_threshold'],
                'CloudCoverMax': self.config['cloud_cover_max'],
                'Source_Images': ', '.join(source_images[:10]) + ('...' if len(source_images) > 10 else ''),
                'Processing_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            result['ndvi_metadata'] = ndvi_metadata
        
        elapsed = time.time() - start_time
        coverage_str = f"{result.get('coverage_percent', 0):.1f}% VC" if output_mode in ['vc', 'both'] else "NDVI only"
        print(f" ✅ {image_count} images, {coverage_str} ({elapsed:.1f}s)")
        
        return result

    def process_all_months(self, month_infos: List[Dict]) -> List[Dict]:
        """Process all months in parallel"""
        print(f"\n🔄 Processing {len(month_infos)} months in parallel...")
        start_time = time.time()
        
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config['max_workers']) as executor:
            future_to_month = {
                executor.submit(self.process_month, month_info): month_info['month']
                for month_info in month_infos
            }
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_month):
                month_num = future_to_month[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1
                    
                    # Show progress
                    if result['image_count'] > 0:
                        coverage_str = f"{result.get('coverage_percent', 0):.1f}% VC" if 'coverage_percent' in result else "NDVI only"
                        print(f"  ✅ Month {month_num}: {result['label']} ({result['image_count']} images, {coverage_str})")
                    else:
                        print(f"  ⚠️ Month {month_num}: {result['label']} (no images)")
                        
                except Exception as e:
                    print(f"  ❌ Month {month_num} failed: {str(e)[:100]}")
                    # Create placeholder for failed month with metadata
                    label = f"{self.config['year']}-{month_num:02d}"
                    output_mode = self.config['output_mode']
                    
                    placeholder = {
                        'month': month_num,
                        'label': label,
                        'image_count': 0,
                        'coverage_percent': 0,
                        'source_images': [],
                        'success': False
                    }
                    
                    if output_mode in ['vc', 'both']:
                        placeholder['vc_mosaic'] = ee.Image.constant(0).rename('vc').clip(self.metro).rename(label)
                        placeholder['metadata'] = {
                            'Year': self.config['year'],
                            'Month': label,
                            'DataType': 'VC',
                            'ImageCount': 0,
                            'CoveragePercent': 0,
                            'VC_Filename': f'VC_{label}_thr_{str(self.config["ndvi_threshold"]).replace(".", "_")}',
                            'Threshold': self.config['ndvi_threshold'],
                            'CloudCoverMax': self.config['cloud_cover_max'],
                            'Source_Images': '',
                            'Processing_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                    
                    if output_mode in ['ndvi', 'both']:
                        placeholder['ndvi_mosaic'] = ee.Image.constant(-9999).rename('ndvi').clip(self.metro).rename(label)
                        placeholder['ndvi_metadata'] = {
                            'Year': self.config['year'],
                            'Month': label,
                            'DataType': 'NDVI_max',
                            'ImageCount': 0,
                            'NDVI_Filename': f'NDVI_{label}_thr_{str(self.config["ndvi_threshold"]).replace(".", "_")}',
                            'Threshold': self.config['ndvi_threshold'],
                            'CloudCoverMax': self.config['cloud_cover_max'],
                            'Source_Images': '',
                            'Processing_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                    
                    results.append(placeholder)
        
        results.sort(key=lambda x: x['month'])
        elapsed_time = time.time() - start_time
        print(f"\n✅ Parallel processing completed in {elapsed_time:.1f} seconds")
        
        return results
    
    def create_annual_composite(self, results: List[Dict], output_type: str = 'vc') -> Optional[ee.Image]:
        """Create annual composite for VC or NDVI"""
        type_label = output_type.upper()
        print(f"\n🎯 Creating annual {type_label} composite...")
        start_time = time.time()
        
        mosaics = []
        labels = []
        
        for result in results:
            if output_type == 'vc' and 'vc_mosaic' in result:
                mosaics.append(result['vc_mosaic'])
                labels.append(result['label'])
            elif output_type == 'ndvi' and 'ndvi_mosaic' in result:
                mosaics.append(result['ndvi_mosaic'])
                labels.append(result['label'])
        
        if not mosaics:
            print(f"  ❌ No {type_label} mosaics available")
            return None
        
        ic = ee.ImageCollection.fromImages(mosaics)
        composite = ic.toBands() \
            .rename(labels) \
            .clip(self.metro) \
            .set({
                'year': self.config['year'],
                'threshold': self.config['ndvi_threshold'],
                'cloud_filter': self.config['cloud_cover_max'],
                'creation_date': datetime.now().strftime('%Y-%m-%d'),
                'description': f'Monthly {type_label} composite {self.config["start_month"]:02d}-{self.config["end_month"]:02d} {self.config["year"]}'
            })
        
        elapsed = time.time() - start_time
        print(f"  ✅ Annual {type_label} composite created ({elapsed:.1f}s)")
        print(f"  📊 Contains {len(mosaics)} monthly bands")
        
        return composite
    
    def export_metadata(self, results: List[Dict], filename: str) -> bool:
        """Export metadata to CSV"""
        import csv
        
        metadata_rows = []
        output_mode = self.config['output_mode']
        
        for result in results:
            if output_mode in ['vc', 'both'] and 'metadata' in result:
                metadata_rows.append(result['metadata'])
            if output_mode in ['ndvi', 'both'] and 'ndvi_metadata' in result:
                metadata_rows.append(result['ndvi_metadata'])
        
        if not metadata_rows:
            print("  ⚠️ No metadata to export")
            return False
        
        output_path = os.path.join(self.config['output_path'], filename)
        
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=metadata_rows[0].keys())
                writer.writeheader()
                writer.writerows(metadata_rows)
            
            print(f"  ✅ Metadata exported to {filename}")
            return True
        except Exception as e:
            print(f"  ❌ Metadata export failed: {str(e)}")
            return False
    
    def run(self) -> Dict[str, Any]:
        """Run monthly processing pipeline - supports VC, NDVI, or both"""
        total_start_time = time.time()
        output_mode = self.config['output_mode']
        
        print("\n" + "=" * 70)
        print("🚀 MONTHLY PROCESSING")
        mode_labels = {
            'vc': '📊 MODE: VC Only',
            'ndvi': '📊 MODE: NDVI Only',
            'both': '📊 MODE: VC + NDVI'
        }
        print(mode_labels.get(output_mode, '📊 MODE: VC Only'))
        print("=" * 70)
        
        # Step 1: Create output directory
        if not create_output_directory(self.config['output_path']):
            return {'success': False, 'error': 'Failed to create output directory'}
        
        # Step 2: Create monthly periods
        month_infos = self.create_monthly_periods()
        
        # Step 3: Process all months
        results = self.process_all_months(month_infos)
        
        # Step 4: Export metadata
        metadata_filename = f"{self.config['year']}_Monthly"
        if output_mode == 'ndvi':
            metadata_filename += "_NDVI"
        elif output_mode == 'both':
            metadata_filename += "_VC_NDVI"
        else:  # 'vc'
            metadata_filename += "_VC"
        metadata_filename += "_Metadata.csv"
        
        metadata_success = self.export_metadata(results, metadata_filename)
        
        # Step 5: Create and export composites
        vc_success = False
        ndvi_success = False
        
        # Handle VC
        if output_mode in ['vc', 'both']:
            annual_vc = self.create_annual_composite(results, 'vc')
            if annual_vc is not None:
                vc_filename = f'VC_Annual_{self.config["year"]}_thr_{str(self.config["ndvi_threshold"]).replace(".", "_")}'
                vc_filename += f'_{self.config["start_month"]:02d}_{self.config["end_month"]:02d}.tif'
                print(f"\n📤 Exporting VC annual composite...")
                print(f"  Filename: {vc_filename}")
                
                num_bands = self.config['end_month'] - self.config['start_month'] + 1
                print(f"  Note: This may take several minutes (contains {num_bands} bands)")
                
                vc_success = self.export_with_geedim(annual_vc, vc_filename)
                
                # File existence check
                if not vc_success:
                    vc_file_path = os.path.join(self.config['output_path'], vc_filename)
                    if os.path.exists(vc_file_path):
                        print(f"  ✅ File exists: {vc_filename}")
                        vc_success = True
        
        # Handle NDVI
        if output_mode in ['ndvi', 'both']:
            annual_ndvi = self.create_annual_composite(results, 'ndvi')
            if annual_ndvi is not None:
                ndvi_filename = f'NDVI_Annual_{self.config["year"]}_thr_{str(self.config["ndvi_threshold"]).replace(".", "_")}'
                ndvi_filename += f'_{self.config["start_month"]:02d}_{self.config["end_month"]:02d}.tif'
                print(f"\n📤 Exporting NDVI annual composite...")
                print(f"  Filename: {ndvi_filename}")
                
                num_bands = self.config['end_month'] - self.config['start_month'] + 1
                print(f"  Note: This may take several minutes (contains {num_bands} bands)")
                
                ndvi_success = self.export_with_geedim(annual_ndvi, ndvi_filename)
                
                # File existence check
                if not ndvi_success:
                    ndvi_file_path = os.path.join(self.config['output_path'], ndvi_filename)
                    if os.path.exists(ndvi_file_path):
                        print(f"  ✅ NDVI file exists: {ndvi_filename}")
                        ndvi_success = True
        
        # Step 6: Generate summary
        total_time = time.time() - total_start_time
        
        print("\n" + "=" * 70)
        print("📊 FINAL SUMMARY")
        print("=" * 70)
        print(f"Total processing time: {total_time:.1f} seconds")
        print(f"Metadata export: {'✅ SUCCESS' if metadata_success else '❌ FAILED'}")
        
        if output_mode in ['vc', 'both']:
            print(f"VC composite export: {'✅ SUCCESS' if vc_success else '❌ FAILED'}")
        if output_mode in ['ndvi', 'both']:
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
        success = metadata_success
        if output_mode in ['vc', 'both']:
            success = success and vc_success
        if output_mode in ['ndvi', 'both']:
            success = success and ndvi_success
        
        return {
            'success': success,
            'processing_time': total_time,
            'metadata_export': metadata_success,
            'vc_composite_export': vc_success if output_mode in ['vc', 'both'] else None,
            'ndvi_composite_export': ndvi_success if output_mode in ['ndvi', 'both'] else None,
            'output_mode': output_mode,
            'months_processed': len(results),
            'months_with_data': sum(1 for r in results if r['image_count'] > 0),
            'total_source_images': sum(r['image_count'] for r in results),
            'output_path': self.config['output_path']
        }