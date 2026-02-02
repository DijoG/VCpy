"""
Core processing functions for VCpy
"""

import ee
import os
import time
import csv
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Any
from .utils import maskS2clouds, addNDVI, export_with_geedim

class VCProcessor:
    """Base class for VC processing"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.metro = ee.FeatureCollection(config['metro_asset'])
        self.region = self.metro.geometry()
        
        # Initialize output path
        self.config['output_path'] = config.get('output_path', 
                                              os.path.join(config['output_base_path'], 
                                                          self.__class__.__name__.lower()))
    
    def process_period(self, period_info: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single period - to be implemented by subclasses"""
        raise NotImplementedError
    
    def export_metadata(self, results: List[Dict[str, Any]], filename: str) -> bool:
        """
        Export metadata to CSV
        
        Args:
            results: List of result dictionaries
            filename: Output CSV filename
            
        Returns:
            bool: True if successful
        """
        full_path = os.path.join(self.config['output_path'], filename)
        
        print(f"\n📊 Exporting metadata to CSV: {filename}")
        
        try:
            # Collect all metadata records
            all_metadata = []
            for result in results:
                if 'metadata' in result:
                    all_metadata.append(result['metadata'])
            
            if not all_metadata:
                print("  ⚠️ No metadata to export")
                return False
            
            # Write to CSV
            with open(full_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = all_metadata[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_metadata)
            
            file_size = os.path.getsize(full_path) / 1024
            print(f"  ✅ Metadata CSV exported: {full_path} ({file_size:.1f} KB)")
            print(f"  📋 {len(all_metadata)} records written")
            
            return True
            
        except Exception as e:
            print(f"  ❌ Failed to export metadata CSV: {str(e)}")
            return False
    
    def run(self) -> Dict[str, Any]:
        """Run the processing pipeline - to be implemented by subclasses"""
        raise NotImplementedError