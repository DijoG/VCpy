"""
Bi-weekly VC processing module
"""

import ee
import os
import time
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Any
from .core import VCProcessor
from .utils import create_output_directory, export_with_geedim, maskS2clouds, addNDVI

def biweek_VCpy(
    service_account_email: str = None,
    service_account_key_file: str = None,
    output_path: str = None,
    year: int = 2025,
    months: int = 12,
    ndvi_threshold: float = 0.15,
    cloud_cover_max: int = 15,
    acquisition_window: int = 21,
    max_workers: int = 4,
    export_ndvi: bool = False,
    metro_asset: str = None,
    crs: str = 'EPSG:32638',
    scale: int = 10,
    dtype: str = 'float32'
):
    """
    Run bi-weekly vegetation cover analysis
    
    Args:
        service_account_email: GEE service account email
        service_account_key_file: Path to service account key file
        output_path: Output directory path
        year: Year to process
        months: Number of months to process (1-12)
        ndvi_threshold: NDVI threshold for vegetation cover
        cloud_cover_max: Maximum cloud cover percentage
        acquisition_window: Acquisition window in days
        max_workers: Number of parallel workers
        export_ndvi: Whether to export NDVI images
        metro_asset: Asset path for metro region
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
    
    config.update({
        'year': year,
        'months': months,
        'ndvi_threshold': ndvi_threshold,
        'cloud_cover_max': cloud_cover_max,
        'acquisition_window': acquisition_window,
        'max_workers': max_workers,
        'export_ndvi': export_ndvi,
        'crs': crs,
        'scale': scale,
        'dtype': dtype,
        'output_path': os.path.join(config['output_base_path'], 'biweekly')
    })
    
    # Initialize Earth Engine
    if not initialize_earth_engine(config):
        return {'success': False, 'error': 'Earth Engine initialization failed'}
    
    # Create processor and run
    processor = BiweeklyProcessor(config)
    return processor.run()


class BiweeklyProcessor(VCProcessor):
    """Processor for bi-weekly VC analysis"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Initialize cloud mask and NDVI functions
        self.maskS2clouds = maskS2clouds
        self.addNDVI = lambda img: addNDVI(img, self.config['ndvi_threshold'])
        self.export_with_geedim = lambda img, filename: export_with_geedim(
            img, filename, self.region, self.config
        )
    
    def create_biweekly_periods(self) -> List[Dict[str, Any]]:
        """Create bi-weekly periods for processing"""
        year = self.config['year']
        months = self.config['months']
        total_periods = months * 2
        periods = []
        
        for period in range(1, total_periods + 1):
            start_day = (period - 1) * 15 + 1
            end_day = min(period * 15, 365)
            
            start_date = ee.Date.fromYMD(year, 1, 1).advance(start_day - 1, 'day')
            output_end = ee.Date.fromYMD(year, 1, 1).advance(end_day - 1, 'day')
            
            periods.append({
                'period': period,
                'start': start_date,
                'output_end': output_end,
                'label': start_date.format('YYYY-MM-dd').getInfo()
            })
        
        print(f'📅 Processing {months} months ({total_periods} bi-weekly periods)')
        print(f'📅 Acquisition window: {self.config["acquisition_window"]} days')
        print(f'⚡ Parallel workers: {self.config["max_workers"]}')
        print(f'📊 NDVI Export: {"ENABLED" if self.config["export_ndvi"] else "DISABLED (VC only)"}')
        
        return periods
    
    def process_period(self, period_info: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single bi-weekly period"""
        period_num = period_info['period']
        label = period_info['label']
        start = period_info['start']
        output_end = period_info['output_end']
        end = start.advance(self.config['acquisition_window'], 'days')
        
        # Get Sentinel-2 image collection
        ic = ee.ImageCollection('COPERNICUS/S2_HARMONIZED') \
            .filterDate(start, end) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', self.config['cloud_cover_max'])) \
            .filterBounds(self.metro)
        
        image_count = ic.size().getInfo()
        
        # Get source image names
        source_names = []
        if image_count > 0:
            source_names = ic.limit(20).aggregate_array('system:index').getInfo()
        
        # Create metadata
        metadata = {
            'Year': self.config['year'],
            'Months_Processed': self.config['months'],
            'Period_Number': period_num,
            'Period_Label': label,
            'Output_Start': start.format('YYYY-MM-dd').getInfo(),
            'Output_End': output_end.format('YYYY-MM-dd').getInfo(),
            'Acquisition_Start': start.format('YYYY-MM-dd').getInfo(),
            'Acquisition_End': end.format('YYYY-MM-dd').getInfo(),
            'Acquisition_Window_Days': self.config['acquisition_window'],
            'Image_Count': image_count,
            'QA_Flag': image_count > 0,
            'Source_Images': ', '.join(source_names[:10]) + ('...' if len(source_names) > 10 else ''),
            'NDVI_Threshold': self.config['ndvi_threshold'],
            'Cloud_Cover_Max': self.config['cloud_cover_max'],
            'Data_Type': 'VC',
            'Processing_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        result = {
            'period': period_num,
            'label': label,
            'image_count': image_count,
            'source_names': source_names,
            'success': True,
            'metadata': metadata
        }
        
        if image_count == 0:
            result['vc_image'] = ee.Image.constant(0).rename('vc').clip(self.metro).rename(label)
            if self.config['export_ndvi']:
                result['ndvi_image'] = ee.Image.constant(-9999).rename('ndvi').clip(self.metro).rename(label)
            return result
        
        # Process images
        processed_ic = ic.map(self.maskS2clouds).map(self.addNDVI)
        
        # Create VC mosaic
        vc_mosaic = processed_ic.select('vc').mosaic() \
            .unmask(0) \
            .clip(self.metro) \
            .round()
        result['vc_image'] = vc_mosaic.rename(label)
        
        # Create NDVI mosaic if needed
        if self.config['export_ndvi']:
            ndvi_mosaic = processed_ic.select('ndvi').mean() \
                .unmask(-9999) \
                .clip(self.metro)
            result['ndvi_image'] = ndvi_mosaic.rename(label)
            
            # Add NDVI metadata
            ndvi_metadata = metadata.copy()
            ndvi_metadata['Data_Type'] = 'NDVI_mean'
            result['ndvi_metadata'] = ndvi_metadata
        
        return result
    
    def process_all_periods(self, period_infos: List[Dict]) -> List[Dict]:
        """Process all periods in parallel"""
        print(f"\n🔄 Processing {len(period_infos)} periods in parallel...")
        start_time = time.time()
        
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config['max_workers']) as executor:
            future_to_period = {
                executor.submit(self.process_period, period_info): period_info['period']
                for period_info in period_infos
            }
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_period):
                period_num = future_to_period[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1
                    
                    qa = "✅" if result['image_count'] > 0 else "⚠️"
                    print(f"  {qa} Period {period_num}: {result['label']} ({result['image_count']} images)")
                    
                except Exception as e:
                    print(f"  ❌ Period {period_num} failed: {str(e)[:100]}")
                    placeholder = {
                        'period': period_num,
                        'label': f'period_{period_num}',
                        'vc_image': ee.Image.constant(0).rename('vc').clip(self.metro)
                                    .rename(f'period_{period_num}'),
                        'image_count': 0,
                        'source_names': [],
                        'success': False,
                        'metadata': {
                            'Year': self.config['year'],
                            'Months_Processed': self.config['months'],
                            'Period_Number': period_num,
                            'Period_Label': f'period_{period_num}',
                            'Image_Count': 0,
                            'QA_Flag': False,
                            'Processing_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                    }
                    if self.config['export_ndvi']:
                        placeholder['ndvi_image'] = ee.Image.constant(-9999).rename('ndvi') \
                                                    .clip(self.metro).rename(f'period_{period_num}')
                    results.append(placeholder)
        
        results.sort(key=lambda x: x['period'])
        elapsed_time = time.time() - start_time
        print(f"\n✅ Parallel processing completed in {elapsed_time:.1f} seconds")
        
        return results
    
    def export_files(self, results: List[Dict]) -> tuple:
        """Export image files"""
        # Define period pairs
        period_pairs = ['01_02', '03_04', '05_06', '07_08', '09_10', 
                       '11_12', '13_14', '15_16', '17_18', '19_20', '21_22', '23_24']
        
        needed_pairs = period_pairs[:self.config['months']]
        
        if self.config['export_ndvi']:
            print(f"\n📊 Exporting {len(needed_pairs)} pairs (VC + NDVI)...")
            total_files = len(needed_pairs) * 2
        else:
            print(f"\n📊 Exporting {len(needed_pairs)} VC pairs (NDVI disabled)...")
            total_files = len(needed_pairs)
        
        print("=" * 70)
        
        # Create output directory
        if not create_output_directory(self.config['output_path']):
            return 0, total_files
        
        export_start = time.time()
        successful_exports = 0
        
        for i, periods in enumerate(needed_pairs):
            start_period = i * 2 + 1
            end_period = i * 2 + 2
            
            if self.config['export_ndvi']:
                print(f"\n📦 Exporting pair {periods} (VC + NDVI)...")
            else:
                print(f"\n📦 Exporting VC pair {periods}...")
            
            # Get results for this pair
            pair_results = [r for r in results if start_period <= r['period'] <= end_period]
            
            if len(pair_results) == 2:
                # Extract VC images
                vc_images = [r['vc_image'] for r in pair_results]
                labels = [r['label'] for r in pair_results]
                
                # Create combined VC image
                vc_combined = ee.ImageCollection(vc_images).toBands().rename(labels).clip(self.metro)
                
                # Export VC image
                vc_filename = f'{self.config["year"]}_BiWeekly_VC_{periods}.tif'
                if self.export_with_geedim(vc_combined, vc_filename):
                    successful_exports += 1
                
                time.sleep(1)
                
                # Export NDVI if enabled
                if self.config['export_ndvi']:
                    ndvi_images = [r['ndvi_image'] for r in pair_results]
                    ndvi_combined = ee.ImageCollection(ndvi_images).toBands().rename(labels).clip(self.metro)
                    ndvi_filename = f'{self.config["year"]}_BiWeekly_NDVI_{periods}.tif'
                    if self.export_with_geedim(ndvi_combined, ndvi_filename):
                        successful_exports += 1
                    time.sleep(1)
            else:
                print(f"  ⚠️ Missing data for pair {periods}")
        
        export_time = time.time() - export_start
        
        if self.config['export_ndvi']:
            print(f"\n✅ Export completed in {export_time:.1f} seconds")
            print(f"   Successful exports: {successful_exports}/{total_files} files (VC + NDVI)")
        else:
            print(f"\n✅ Export completed in {export_time:.1f} seconds")
            print(f"   Successful VC exports: {successful_exports}/{total_files} files")
        
        return successful_exports, total_files
    
    def run(self) -> Dict[str, Any]:
        """Run bi-weekly processing pipeline"""
        total_start_time = time.time()
        
        print("\n" + "=" * 70)
        print("🚀 BI-WEEKLY VC PROCESSING")
        print("=" * 70)
        
        # Step 1: Create output directory
        if not create_output_directory(self.config['output_path']):
            return {'success': False, 'error': 'Failed to create output directory'}
        
        # Step 2: Create periods
        period_infos = self.create_biweekly_periods()
        
        # Step 3: Process periods
        results = self.process_all_periods(period_infos)
        
        # Step 4: Export metadata
        metadata_filename = f"{self.config['year']}_BiWeekly_VC_NDVI_Metadata.csv"
        metadata_success = self.export_metadata(results, metadata_filename)
        
        # Step 5: Export files
        successful_exports, total_files = self.export_files(results)
        
        # Step 6: Generate summary
        total_time = time.time() - total_start_time
        
        print("\n" + "=" * 70)
        print("📊 FINAL SUMMARY")
        print("=" * 70)
        print(f"Total processing time: {total_time:.1f} seconds")
        print(f"Successful image exports: {successful_exports}/{total_files} files")
        print(f"Metadata export: {'✅ SUCCESS' if metadata_success else '❌ FAILED'}")
        
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
        
        success = successful_exports == total_files and metadata_success
        
        return {
            'success': success,
            'processing_time': total_time,
            'image_exports': f"{successful_exports}/{total_files}",
            'metadata_export': metadata_success,
            'output_path': self.config['output_path']
        }