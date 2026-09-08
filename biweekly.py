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
    start_month: int = 1,  # New: Start month
    end_month: int = 12,   # New: End month
    ndvi_threshold: float = 0.15,
    cloud_cover_max: int = 15,
    acquisition_window: int = 21,
    max_workers: int = 4,
    output_mode: str = 'vc',  # 'vc', 'ndvi', or 'both'
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
        start_month: Starting month (1-12)
        end_month: Ending month (1-12)
        ndvi_threshold: NDVI threshold for vegetation cover
        cloud_cover_max: Maximum cloud cover percentage
        acquisition_window: Acquisition window in days
        max_workers: Number of parallel workers
        output_mode: Output type - 'vc' (VC only), 'ndvi' (NDVI only), or 'both' (VC + NDVI)
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
    
    # Validate month range
    if start_month < 1 or start_month > 12:
        raise ValueError(f"start_month must be between 1 and 12, got {start_month}")
    if end_month < 1 or end_month > 12:
        raise ValueError(f"end_month must be between 1 and 12, got {end_month}")
    if start_month > end_month:
        raise ValueError(f"start_month ({start_month}) must be <= end_month ({end_month})")
    
    # Calculate number of months
    months = end_month - start_month + 1
    
    config.update({
        'year': year,
        'start_month': start_month,  # New
        'end_month': end_month,      # New
        'months': months,            # Calculated from range
        'ndvi_threshold': ndvi_threshold,
        'cloud_cover_max': cloud_cover_max,
        'acquisition_window': acquisition_window,
        'max_workers': max_workers,
        'output_mode': output_mode,
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
        """Create bi-weekly periods for processing based on month range"""
        year = self.config['year']
        start_month = self.config['start_month']
        end_month = self.config['end_month']
        
        # Create date range for the specified months
        start_date = ee.Date.fromYMD(year, start_month, 1)
        end_date = ee.Date.fromYMD(year, end_month, 1).advance(1, 'month')
        
        periods = []
        current_date = start_date
        
        while current_date.millis().getInfo() < end_date.millis().getInfo():
            period_num = len(periods) + 1
            
            # Get the day of year for current date
            day_of_year = current_date.getRelative('day', 'year').getInfo()
            
            # Calculate period start (every 15 days)
            period_start_day = (period_num - 1) * 15 + 1
            
            # Calculate actual start date for this period (relative to year start)
            period_start = ee.Date.fromYMD(year, 1, 1).advance(period_start_day - 1, 'day')
            
            # Check if this period falls within our month range
            if period_start.millis().getInfo() >= end_date.millis().getInfo():
                break
            
            # If period_start is before start_date, use start_date as the reference
            actual_start = period_start
            if actual_start.millis().getInfo() < start_date.millis().getInfo():
                actual_start = start_date
            
            # Calculate output end (15 days after start)
            output_end = period_start.advance(14, 'day')
            
            # Only add if the period overlaps with our date range
            if output_end.millis().getInfo() >= start_date.millis().getInfo():
                periods.append({
                    'period': period_num,
                    'start': actual_start,
                    'output_end': output_end,
                    'label': actual_start.format('YYYY-MM-dd').getInfo()
                })
            
            # Move to next period
            current_date = period_start.advance(15, 'day')
        
        # If we have more than 24 periods (12 months), limit to 24
        if len(periods) > 24:
            periods = periods[:24]
        
        total_periods = len(periods)
        months = self.config['months']
        
        print(f'📅 Processing months {start_month} to {end_month} ({months} months)')
        print(f'📅 Total bi-weekly periods: {total_periods}')
        print(f'📅 Acquisition window: {self.config["acquisition_window"]} days')
        print(f'⚡ Parallel workers: {self.config["max_workers"]}')
        
        output_mode = self.config['output_mode']
        mode_labels = {
            'vc': 'VC Only',
            'ndvi': 'NDVI Only',
            'both': 'VC + NDVI'
        }
        print(f'📊 Output Mode: {mode_labels.get(output_mode, "VC Only")}')
        
        return periods
    
    def process_period(self, period_info: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single bi-weekly period"""
        period_num = period_info['period']
        label = period_info['label']
        start = period_info['start']
        output_end = period_info['output_end']
        end = start.advance(self.config['acquisition_window'], 'days')
        output_mode = self.config['output_mode']
        
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
        
        # Create base metadata
        base_metadata = {
            'Year': self.config['year'],
            'Start_Month': self.config['start_month'],
            'End_Month': self.config['end_month'],
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
            'Processing_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        result = {
            'period': period_num,
            'label': label,
            'image_count': image_count,
            'source_names': source_names,
            'success': True
        }
        
        if image_count == 0:
            # Create placeholder images based on mode
            if output_mode in ['vc', 'both']:
                result['vc_image'] = ee.Image.constant(0).rename('vc').clip(self.metro).rename(label)
                result['metadata'] = base_metadata.copy()
                result['metadata']['Data_Type'] = 'VC'
            
            if output_mode in ['ndvi', 'both']:
                result['ndvi_image'] = ee.Image.constant(-9999).rename('ndvi').clip(self.metro).rename(label)
                ndvi_metadata = base_metadata.copy()
                ndvi_metadata['Data_Type'] = 'NDVI_mean'
                result['ndvi_metadata'] = ndvi_metadata
            
            return result
        
        # Process images
        processed_ic = ic.map(self.maskS2clouds).map(self.addNDVI)
        
        # Create VC mosaic if needed
        if output_mode in ['vc', 'both']:
            vc_mosaic = processed_ic.select('vc').mosaic() \
                .unmask(0) \
                .clip(self.metro) \
                .round()
            result['vc_image'] = vc_mosaic.rename(label)
            
            vc_metadata = base_metadata.copy()
            vc_metadata['Data_Type'] = 'VC'
            result['metadata'] = vc_metadata
        
        # Create NDVI mosaic if needed
        if output_mode in ['ndvi', 'both']:
            ndvi_mosaic = processed_ic.select('ndvi').mean() \
                .unmask(-9999) \
                .clip(self.metro)
            result['ndvi_image'] = ndvi_mosaic.rename(label)
            
            ndvi_metadata = base_metadata.copy()
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
                    output_mode = self.config['output_mode']
                    placeholder = {
                        'period': period_num,
                        'label': f'period_{period_num}',
                        'image_count': 0,
                        'source_names': [],
                        'success': False
                    }
                    
                    if output_mode in ['vc', 'both']:
                        placeholder['vc_image'] = ee.Image.constant(0).rename('vc').clip(self.metro).rename(f'period_{period_num}')
                        placeholder['metadata'] = {
                            'Year': self.config['year'],
                            'Start_Month': self.config['start_month'],
                            'End_Month': self.config['end_month'],
                            'Period_Number': period_num,
                            'Period_Label': f'period_{period_num}',
                            'Image_Count': 0,
                            'QA_Flag': False,
                            'Data_Type': 'VC',
                            'Processing_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                    
                    if output_mode in ['ndvi', 'both']:
                        placeholder['ndvi_image'] = ee.Image.constant(-9999).rename('ndvi').clip(self.metro).rename(f'period_{period_num}')
                        placeholder['ndvi_metadata'] = {
                            'Year': self.config['year'],
                            'Start_Month': self.config['start_month'],
                            'End_Month': self.config['end_month'],
                            'Period_Number': period_num,
                            'Period_Label': f'period_{period_num}',
                            'Image_Count': 0,
                            'QA_Flag': False,
                            'Data_Type': 'NDVI_mean',
                            'Processing_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                    
                    results.append(placeholder)
        
        results.sort(key=lambda x: x['period'])
        elapsed_time = time.time() - start_time
        print(f"\n✅ Parallel processing completed in {elapsed_time:.1f} seconds")
        
        return results
    
    def export_files(self, results: List[Dict]) -> tuple:
        """Export image files"""
        # Define period pairs (up to 24 periods for 12 months)
        period_pairs = ['01_02', '03_04', '05_06', '07_08', '09_10', 
                       '11_12', '13_14', '15_16', '17_18', '19_20', '21_22', '23_24']
        
        # Calculate how many periods we actually processed
        total_periods = len(results)
        needed_pairs = period_pairs[:total_periods // 2]
        
        output_mode = self.config['output_mode']
        
        # Calculate total files based on mode
        if output_mode == 'vc':
            total_files = len(needed_pairs)
            mode_desc = "VC"
        elif output_mode == 'ndvi':
            total_files = len(needed_pairs)
            mode_desc = "NDVI"
        else:  # 'both'
            total_files = len(needed_pairs) * 2
            mode_desc = "VC + NDVI"
        
        print(f"\n📊 Exporting {len(needed_pairs)} pairs ({mode_desc})...")
        print("=" * 70)
        
        # Create output directory
        if not create_output_directory(self.config['output_path']):
            return 0, total_files
        
        export_start = time.time()
        successful_exports = 0
        
        for i, periods in enumerate(needed_pairs):
            start_period = i * 2 + 1
            end_period = i * 2 + 2
            
            if output_mode == 'both':
                print(f"\n📦 Exporting pair {periods} (VC + NDVI)...")
            elif output_mode == 'ndvi':
                print(f"\n📦 Exporting NDVI pair {periods}...")
            else:
                print(f"\n📦 Exporting VC pair {periods}...")
            
            # Get results for this pair
            pair_results = [r for r in results if start_period <= r['period'] <= end_period]
            
            if len(pair_results) == 2:
                # Export VC if needed
                if output_mode in ['vc', 'both']:
                    vc_images = [r['vc_image'] for r in pair_results if 'vc_image' in r]
                    if len(vc_images) == 2:
                        labels = [r['label'] for r in pair_results]
                        vc_combined = ee.ImageCollection(vc_images).toBands().rename(labels).clip(self.metro)
                        vc_filename = f"{self.config['year']}_BiWeekly_VC_{periods}.tif"
                        if self.export_with_geedim(vc_combined, vc_filename):
                            successful_exports += 1
                        time.sleep(1)
                
                # Export NDVI if needed
                if output_mode in ['ndvi', 'both']:
                    ndvi_images = [r['ndvi_image'] for r in pair_results if 'ndvi_image' in r]
                    if len(ndvi_images) == 2:
                        labels = [r['label'] for r in pair_results]
                        ndvi_combined = ee.ImageCollection(ndvi_images).toBands().rename(labels).clip(self.metro)
                        ndvi_filename = f"{self.config['year']}_BiWeekly_NDVI_{periods}.tif"
                        if self.export_with_geedim(ndvi_combined, ndvi_filename):
                            successful_exports += 1
                        time.sleep(1)
            else:
                print(f"  ⚠️ Missing data for pair {periods}")
        
        export_time = time.time() - export_start
        
        print(f"\n✅ Export completed in {export_time:.1f} seconds")
        print(f"   Successful exports: {successful_exports}/{total_files} files ({mode_desc})")
        
        return successful_exports, total_files
    
    def export_metadata(self, results: List[Dict], filename: str) -> bool:
        """Export metadata to CSV - handles both VC and NDVI metadata"""
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
        """Run bi-weekly processing pipeline"""
        total_start_time = time.time()
        output_mode = self.config['output_mode']
        
        print("\n" + "=" * 70)
        print("🚀 BI-WEEKLY PROCESSING")
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
        
        # Step 2: Create periods
        period_infos = self.create_biweekly_periods()
        
        # Step 3: Process periods
        results = self.process_all_periods(period_infos)
        
        # Step 4: Export metadata
        metadata_filename = f"{self.config['year']}_BiWeekly"
        if output_mode == 'ndvi':
            metadata_filename += "_NDVI"
        elif output_mode == 'both':
            metadata_filename += "_VC_NDVI"
        else:  # 'vc'
            metadata_filename += "_VC"
        metadata_filename += f"_{self.config['start_month']:02d}_{self.config['end_month']:02d}_Metadata.csv"
        
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
            'output_path': self.config['output_path'],
            'output_mode': output_mode,
            'start_month': self.config['start_month'],
            'end_month': self.config['end_month']
        }