"""
Bi-weekly VC processing module
"""

import ee
import os
import time
import concurrent.futures
from datetime import date, timedelta, datetime
from typing import List, Dict, Any
from .core import VCProcessor
from .utils import create_output_directory, export_with_geedim, maskS2clouds, addNDVI


def biweek_VCpy(
    service_account_email: str = None,
    service_account_key_file: str = None,
    output_path: str = None,
    year: int = 2025,
    start_month: int = 1,
    end_month: int = 12,
    ndvi_threshold: float = 0.15,
    cloud_cover_max: int = 15,
    acquisition_window: int = 21,
    max_workers: int = 4,
    output_mode: str = 'vc',
    metro_asset: str = None,
    crs: str = 'EPSG:32638',
    scale: int = 10,
    dtype: str = 'float32'
):
    """Run bi-weekly vegetation cover analysis"""
    from .config import DEFAULT_CONFIG
    from .utils import initialize_earth_engine, suppress_warnings

    suppress_warnings()

    config = DEFAULT_CONFIG.copy()

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

    if start_month < 1 or start_month > 12:
        raise ValueError(f"start_month must be between 1 and 12, got {start_month}")
    if end_month < 1 or end_month > 12:
        raise ValueError(f"end_month must be between 1 and 12, got {end_month}")
    if start_month > end_month:
        raise ValueError(f"start_month ({start_month}) must be <= end_month ({end_month})")

    months = end_month - start_month + 1

    config.update({
        'year': year,
        'start_month': start_month,
        'end_month': end_month,
        'months': months,
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

    if not initialize_earth_engine(config):
        return {'success': False, 'error': 'Earth Engine initialization failed'}

    processor = BiweeklyProcessor(config)
    return processor.run()


class BiweeklyProcessor(VCProcessor):
    """Processor for bi-weekly VC analysis"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.maskS2clouds = maskS2clouds
        self.addNDVI = lambda img: addNDVI(img, self.config['ndvi_threshold'])
        self.export_with_geedim = lambda img, filename: export_with_geedim(
            img, filename, self.region, self.config
        )

    def create_biweekly_periods(self) -> List[Dict[str, Any]]:
        """
        Create bi-weekly periods using pure Python date math.

        Periods are numbered from the START OF THE YEAR, not from start_month ->
        -> bi-weekly acquisition dates can fall on 27-31 of previous month!
        """
        year = self.config['year']
        start_month = self.config['start_month']
        end_month = self.config['end_month']

        # Full-year anchor for period numbering
        year_start = date(year, 1, 1)

        # Requested range bounds
        range_start = date(year, start_month, 1)
        if end_month == 12:
            range_end = date(year + 1, 1, 1)
        else:
            range_end = date(year, end_month + 1, 1)

        periods = []
        # Enumerate EVERY 15-day slot in the year, but only keep those that
        # overlap the requested range. Period number = slot index (1-based).
        slot_index = 0
        current = year_start
        while current < range_end:
            slot_index += 1
            slot_start = current
            slot_end = slot_start + timedelta(days=14)

            # Keep this slot only if it overlaps the requested month range
            if slot_end >= range_start and slot_start < range_end:
                periods.append({
                    'period': slot_index,                       # year-anchored!
                    'start': ee.Date(slot_start.isoformat()),
                    'output_end': ee.Date(slot_end.isoformat()),
                    'label': slot_start.isoformat()
                })

            current = current + timedelta(days=15)

        # Cap at 24 periods (full year)
        if len(periods) > 24:
            periods = periods[:24]

        total_periods = len(periods)
        months = self.config['months']

        print(f'📅 Processing months {start_month} to {end_month} ({months} months)')
        print(f'📅 Total bi-weekly periods: {total_periods} '
            f'(numbered {periods[0]["period"]}..{periods[-1]["period"]} of the year)')
        print(f'📅 Acquisition window: {self.config["acquisition_window"]} days')
        print(f'⚡ Parallel workers: {self.config["max_workers"]}')

        output_mode = self.config['output_mode']
        mode_labels = {'vc': 'VC Only', 'ndvi': 'NDVI Only', 'both': 'VC + NDVI'}
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

        t0 = time.time()
        print(f"  ⏳ Period {period_num} ({label}): querying Sentinel-2...", flush=True)

        ic = ee.ImageCollection('COPERNICUS/S2_HARMONIZED') \
            .filterDate(start, end) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', self.config['cloud_cover_max'])) \
            .filterBounds(self.metro)

        image_count = ic.size().getInfo()
        print(f"  📥 Period {period_num} ({label}): {image_count} images found ({time.time()-t0:.1f}s)", flush=True)

        # Safe source names extraction (mirrors monthly.py pattern)
        source_names = []
        if image_count > 0:
            try:
                source_names = ic.limit(20).aggregate_array('system:index').getInfo()
            except Exception as e:
                print(f"  ⚠️ Period {period_num}: could not fetch source names: {str(e)[:80]}")

        base_metadata = {
            'Year': self.config['year'],
            'Start_Month': self.config['start_month'],
            'End_Month': self.config['end_month'],
            'Period_Number': period_num,
            'Period_Label': label,
            'Output_Start': label,
            'Output_End': (date.fromisoformat(label) + timedelta(days=14)).isoformat(),
            'Acquisition_Start': label,
            'Acquisition_End': (date.fromisoformat(label) +
                                timedelta(days=self.config['acquisition_window'])).isoformat(),
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
            if output_mode in ['vc', 'both']:
                result['vc_image'] = ee.Image.constant(0).rename('vc').clip(self.metro).rename(label)
                meta = base_metadata.copy()
                meta['Data_Type'] = 'VC'
                result['metadata'] = meta
            if output_mode in ['ndvi', 'both']:
                result['ndvi_image'] = ee.Image.constant(-9999).rename('ndvi').clip(self.metro).rename(label)
                meta = base_metadata.copy()
                meta['Data_Type'] = 'NDVI_mean'
                result['ndvi_metadata'] = meta
            return result

        processed_ic = ic.map(self.maskS2clouds).map(self.addNDVI)

        if output_mode in ['vc', 'both']:
            vc_mosaic = processed_ic.select('vc').mosaic() \
                .unmask(0) \
                .clip(self.metro) \
                .round()
            result['vc_image'] = vc_mosaic.rename(label)
            meta = base_metadata.copy()
            meta['Data_Type'] = 'VC'
            result['metadata'] = meta

        if output_mode in ['ndvi', 'both']:
            ndvi_mosaic = processed_ic.select('ndvi').mean() \
                .unmask(-9999) \
                .clip(self.metro)
            result['ndvi_image'] = ndvi_mosaic.rename(label)
            meta = base_metadata.copy()
            meta['Data_Type'] = 'NDVI_mean'
            result['ndvi_metadata'] = meta

        return result

    def process_all_periods(self, period_infos: List[Dict]) -> List[Dict]:
        """Process all periods in parallel, with progress prints"""
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
                    print(f"  {qa} Period {period_num}: {result['label']} ({result['image_count']} images) "
                          f"[{completed}/{len(period_infos)}]")
                except Exception as e:
                    print(f"  ❌ Period {period_num} failed: {str(e)[:150]}")
                    output_mode = self.config['output_mode']
                    label = f'period_{period_num}'
                    placeholder = {
                        'period': period_num,
                        'label': label,
                        'image_count': 0,
                        'source_names': [],
                        'success': False
                    }
                    if output_mode in ['vc', 'both']:
                        placeholder['vc_image'] = ee.Image.constant(0).rename('vc').clip(self.metro).rename(label)
                        placeholder['metadata'] = {
                            'Year': self.config['year'],
                            'Start_Month': self.config['start_month'],
                            'End_Month': self.config['end_month'],
                            'Period_Number': period_num,
                            'Period_Label': label,
                            'Image_Count': 0,
                            'QA_Flag': False,
                            'Data_Type': 'VC',
                            'Processing_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                    if output_mode in ['ndvi', 'both']:
                        placeholder['ndvi_image'] = ee.Image.constant(-9999).rename('ndvi').clip(self.metro).rename(label)
                        placeholder['ndvi_metadata'] = {
                            'Year': self.config['year'],
                            'Start_Month': self.config['start_month'],
                            'End_Month': self.config['end_month'],
                            'Period_Number': period_num,
                            'Period_Label': label,
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
        """Export image files, named by year-anchored period numbers"""
        output_mode = self.config['output_mode']

        # Sort by period number (which is year-anchored)
        sorted_results = sorted(results, key=lambda x: x['period'])

        # Pair them by consecutive positions in the SORTED list, but use the
        # actual period numbers for the filename tag.
        pairs = [sorted_results[i:i + 2] for i in range(0, len(sorted_results), 2)]

        if output_mode == 'vc':
            total_files = len(pairs)
            mode_desc = "VC"
        elif output_mode == 'ndvi':
            total_files = len(pairs)
            mode_desc = "NDVI"
        else:
            total_files = len(pairs) * 2
            mode_desc = "VC + NDVI"

        print(f"\n📊 Exporting {len(pairs)} pairs ({mode_desc})...")
        print("=" * 70)

        if not create_output_directory(self.config['output_path']):
            return 0, total_files

        export_start = time.time()
        successful_exports = 0

        for pair_results in pairs:
            if len(pair_results) < 2:
                print(f"  ⚠️ Skipping incomplete pair "
                    f"(periods {[r['period'] for r in pair_results]})")
                continue

            p1 = pair_results[0]['period']
            p2 = pair_results[1]['period']
            periods_tag = f"{p1:02d}_{p2:02d}"      # e.g. periods 11,12 -> "11_12"

            date_a = pair_results[0]['label']
            date_b = pair_results[1]['label']

            if output_mode == 'both':
                print(f"\n📦 Exporting pair {periods_tag} ({date_a} + {date_b}) (VC + NDVI)...")
            elif output_mode == 'ndvi':
                print(f"\n📦 Exporting NDVI pair {periods_tag} ({date_a} + {date_b})...")
            else:
                print(f"\n📦 Exporting VC pair {periods_tag} ({date_a} + {date_b})...")

            if output_mode in ['vc', 'both']:
                vc_images = [r['vc_image'] for r in pair_results if 'vc_image' in r]
                if len(vc_images) == 2:
                    labels = [r['label'] for r in pair_results]
                    vc_combined = ee.ImageCollection(vc_images).toBands().rename(labels).clip(self.metro)
                    vc_filename = f"{self.config['year']}_BiWeekly_VC_{periods_tag}.tif"
                    if self.export_with_geedim(vc_combined, vc_filename):
                        successful_exports += 1
                    time.sleep(1)

            if output_mode in ['ndvi', 'both']:
                ndvi_images = [r['ndvi_image'] for r in pair_results if 'ndvi_image' in r]
                if len(ndvi_images) == 2:
                    labels = [r['label'] for r in pair_results]
                    ndvi_combined = ee.ImageCollection(ndvi_images).toBands().rename(labels).clip(self.metro)
                    ndvi_filename = f"{self.config['year']}_BiWeekly_NDVI_{periods_tag}.tif"
                    if self.export_with_geedim(ndvi_combined, ndvi_filename):
                        successful_exports += 1
                    time.sleep(1)

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

        if not create_output_directory(self.config['output_path']):
            return {'success': False, 'error': 'Failed to create output directory'}

        # Step 2: Create periods (now instant — pure Python date math)
        period_infos = self.create_biweekly_periods()

        # Step 3: Process periods (has per-period progress prints)
        results = self.process_all_periods(period_infos)

        # Step 4: Export metadata
        metadata_filename = f"{self.config['year']}_BiWeekly"
        if output_mode == 'ndvi':
            metadata_filename += "_NDVI"
        elif output_mode == 'both':
            metadata_filename += "_VC_NDVI"
        else:
            metadata_filename += "_VC"
        metadata_filename += f"_{self.config['start_month']:02d}_{self.config['end_month']:02d}_Metadata.csv"

        metadata_success = self.export_metadata(results, metadata_filename)

        # Step 5: Export files
        successful_exports, total_files = self.export_files(results)

        # Step 6: Summary
        total_time = time.time() - total_start_time

        print("\n" + "=" * 70)
        print("📊 FINAL SUMMARY")
        print("=" * 70)
        print(f"Total processing time: {total_time:.1f} seconds")
        print(f"Successful image exports: {successful_exports}/{total_files} files")
        print(f"Metadata export: {'✅ SUCCESS' if metadata_success else '❌ FAILED'}")

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