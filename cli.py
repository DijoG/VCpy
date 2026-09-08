"""
Command Line Interface for VCpy
"""

import argparse
import sys
import os

# Fix for running from any directory
# Add the parent directory to path if running from inside VCpy
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from VCpy.biweekly import biweek_VCpy
from VCpy.monthly import month_VCpy

def run_biweekly():
    """Run bi-weekly VC analysis from command line"""
    parser = argparse.ArgumentParser(
        description='Run bi-weekly vegetation cover analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --year 2025 --start-month 1 --end-month 12
  %(prog)s --year 2024 --start-month 3 --end-month 9 --output-path /path/to/output
  %(prog)s --year 2024 --output-mode ndvi --start-month 1 --end-month 6
  %(prog)s --year 2024 --output-mode both --start-month 1 --end-month 12 --acquisition-window 30
        """
    )
    
    parser.add_argument('--year', type=int, default=2025,
                       help='Year to process (default: 2025)')
    parser.add_argument('--start-month', type=int, default=1, choices=range(1, 13),
                       help='Starting month (1-12, default: 1)')
    parser.add_argument('--end-month', type=int, default=12, choices=range(1, 13),
                       help='Ending month (1-12, default: 12)')
    parser.add_argument('--output-path', help='Custom output directory path')
    parser.add_argument('--ndvi-threshold', type=float, default=0.15,
                       help='NDVI threshold for vegetation cover (default: 0.15)')
    parser.add_argument('--cloud-cover-max', type=int, default=40,
                       help='Maximum cloud cover percentage (default: 40)')
    parser.add_argument('--acquisition-window', type=int, default=21,
                       help='Acquisition window in days (default: 21)')
    parser.add_argument('--max-workers', type=int, default=4,
                       help='Number of parallel workers (default: 4)')
    parser.add_argument('--output-mode', type=str, choices=['vc', 'ndvi', 'both'], default='vc',
                       help='Output mode: vc (VC only), ndvi (NDVI only), or both (default: vc)')
    parser.add_argument('--metro-asset', type=str,
                       help='GEE asset path for metro region (overrides config)')
    parser.add_argument('--crs', type=str, default='EPSG:32638',
                       help='Coordinate reference system (default: EPSG:32638)')
    parser.add_argument('--scale', type=int, default=10,
                       help='Pixel scale in meters (default: 10)')
    parser.add_argument('--dtype', type=str, default='float32',
                       help='Data type for export (default: float32)')
    
    args = parser.parse_args()
    
    # Validate month range
    if args.start_month > args.end_month:
        parser.error("start-month must be <= end-month")
    
    print(f"🚀 Starting bi-weekly VC analysis for {args.year} (months {args.start_month}-{args.end_month})")
    print(f"📊 Output Mode: {args.output_mode.upper()}")
    print(f"📅 Acquisition Window: {args.acquisition_window} days")
    
    result = biweek_VCpy(
        year=args.year,
        start_month=args.start_month,
        end_month=args.end_month,
        output_path=args.output_path,
        ndvi_threshold=args.ndvi_threshold,
        cloud_cover_max=args.cloud_cover_max,
        acquisition_window=args.acquisition_window,
        max_workers=args.max_workers,
        output_mode=args.output_mode,
        metro_asset=args.metro_asset,
        crs=args.crs,
        scale=args.scale,
        dtype=args.dtype
    )
    
    if result.get('success'):
        print(f"✅ Analysis completed successfully!")
        print(f"   Output: {result.get('output_path')}")
        sys.exit(0)
    else:
        print(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)

def run_monthly():
    """Run monthly VC analysis from command line"""
    parser = argparse.ArgumentParser(
        description='Run monthly vegetation cover analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --year 2025
  %(prog)s --year 2024 --start-month 3 --end-month 9 --output-path /path/to/output
  %(prog)s --year 2024 --output-mode ndvi --start-month 1 --end-month 6
  %(prog)s --year 2024 --output-mode both --start-month 1 --end-month 12
        """
    )
    
    parser.add_argument('--year', type=int, default=2025,
                       help='Year to process (default: 2025)')
    parser.add_argument('--start-month', type=int, default=1, choices=range(1, 13),
                       help='Starting month (1-12, default: 1)')
    parser.add_argument('--end-month', type=int, default=12, choices=range(1, 13),
                       help='Ending month (1-12, default: 12)')
    parser.add_argument('--output-path', help='Custom output directory path')
    parser.add_argument('--ndvi-threshold', type=float, default=0.15,
                       help='NDVI threshold for vegetation cover (default: 0.15)')
    parser.add_argument('--cloud-cover-max', type=int, default=15,
                       help='Maximum cloud cover percentage (default: 15)')
    parser.add_argument('--max-workers', type=int, default=4,
                       help='Number of parallel workers (default: 4)')
    parser.add_argument('--output-mode', type=str, choices=['vc', 'ndvi', 'both'], default='vc',
                       help='Output mode: vc (VC only), ndvi (NDVI only), or both (default: vc)')
    parser.add_argument('--metro-asset', type=str,
                       help='GEE asset path for metro region (overrides config)')
    parser.add_argument('--aoi-asset', type=str,
                       help='GEE asset path for AOI region (overrides config)')
    parser.add_argument('--crs', type=str, default='EPSG:32638',
                       help='Coordinate reference system (default: EPSG:32638)')
    parser.add_argument('--scale', type=int, default=10,
                       help='Pixel scale in meters (default: 10)')
    parser.add_argument('--dtype', type=str, default='float32',
                       help='Data type for export (default: float32)')
    
    args = parser.parse_args()
    
    # Validate month range
    if args.start_month > args.end_month:
        parser.error("start-month must be <= end-month")
    
    print(f"🚀 Starting monthly VC analysis for {args.year} (months {args.start_month}-{args.end_month})")
    print(f"📊 Output Mode: {args.output_mode.upper()}")
    
    result = month_VCpy(
        year=args.year,
        start_month=args.start_month,
        end_month=args.end_month,
        output_path=args.output_path,
        ndvi_threshold=args.ndvi_threshold,
        cloud_cover_max=args.cloud_cover_max,
        max_workers=args.max_workers,
        output_mode=args.output_mode,
        metro_asset=args.metro_asset,
        aoi_asset=args.aoi_asset,
        crs=args.crs,
        scale=args.scale,
        dtype=args.dtype
    )
    
    if result.get('success'):
        print(f"✅ Analysis completed successfully!")
        print(f"   Output: {result.get('output_path')}")
        print(f"   Months processed: {result.get('months_processed', 0)}")
        print(f"   Months with data: {result.get('months_with_data', 0)}")
        sys.exit(0)
    else:
        print(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)

def main():
    """Main CLI entry point with subcommands"""
    parser = argparse.ArgumentParser(
        description='VCpy - Vegetation Cover Analysis Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s monthly --year 2025 --output-mode ndvi
  %(prog)s biweekly --year 2024 --start-month 1 --end-month 6 --output-mode ndvi
  %(prog)s biweekly --year 2024 --start-month 6 --end-month 9 --output-mode both --acquisition-window 30
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Monthly subcommand
    monthly_parser = subparsers.add_parser('monthly', help='Run monthly analysis')
    monthly_parser.add_argument('--year', type=int, default=2025,
                               help='Year to process (default: 2025)')
    monthly_parser.add_argument('--start-month', type=int, default=1, choices=range(1, 13),
                               help='Starting month (1-12, default: 1)')
    monthly_parser.add_argument('--end-month', type=int, default=12, choices=range(1, 13),
                               help='Ending month (1-12, default: 12)')
    monthly_parser.add_argument('--output-path', help='Custom output directory path')
    monthly_parser.add_argument('--ndvi-threshold', type=float, default=0.15,
                               help='NDVI threshold for vegetation cover (default: 0.15)')
    monthly_parser.add_argument('--cloud-cover-max', type=int, default=15,
                               help='Maximum cloud cover percentage (default: 15)')
    monthly_parser.add_argument('--max-workers', type=int, default=4,
                               help='Number of parallel workers (default: 4)')
    monthly_parser.add_argument('--output-mode', type=str, choices=['vc', 'ndvi', 'both'], default='vc',
                               help='Output mode: vc (VC only), ndvi (NDVI only), or both (default: vc)')
    monthly_parser.add_argument('--metro-asset', type=str,
                               help='GEE asset path for metro region (overrides config)')
    monthly_parser.add_argument('--aoi-asset', type=str,
                               help='GEE asset path for AOI region (overrides config)')
    monthly_parser.add_argument('--crs', type=str, default='EPSG:32638',
                               help='Coordinate reference system (default: EPSG:32638)')
    monthly_parser.add_argument('--scale', type=int, default=10,
                               help='Pixel scale in meters (default: 10)')
    monthly_parser.add_argument('--dtype', type=str, default='float32',
                               help='Data type for export (default: float32)')
    
    # Biweekly subcommand
    biweekly_parser = subparsers.add_parser('biweekly', help='Run bi-weekly analysis')
    biweekly_parser.add_argument('--year', type=int, default=2025,
                                help='Year to process (default: 2025)')
    biweekly_parser.add_argument('--start-month', type=int, default=1, choices=range(1, 13),
                                help='Starting month (1-12, default: 1)')
    biweekly_parser.add_argument('--end-month', type=int, default=12, choices=range(1, 13),
                                help='Ending month (1-12, default: 12)')
    biweekly_parser.add_argument('--output-path', help='Custom output directory path')
    biweekly_parser.add_argument('--ndvi-threshold', type=float, default=0.15,
                                help='NDVI threshold for vegetation cover (default: 0.15)')
    biweekly_parser.add_argument('--cloud-cover-max', type=int, default=40,
                                help='Maximum cloud cover percentage (default: 40)')
    biweekly_parser.add_argument('--acquisition-window', type=int, default=21,
                                help='Acquisition window in days (default: 21)')
    biweekly_parser.add_argument('--max-workers', type=int, default=4,
                                help='Number of parallel workers (default: 4)')
    biweekly_parser.add_argument('--output-mode', type=str, choices=['vc', 'ndvi', 'both'], default='vc',
                                help='Output mode: vc (VC only), ndvi (NDVI only), or both (default: vc)')
    biweekly_parser.add_argument('--metro-asset', type=str,
                                help='GEE asset path for metro region (overrides config)')
    biweekly_parser.add_argument('--crs', type=str, default='EPSG:32638',
                                help='Coordinate reference system (default: EPSG:32638)')
    biweekly_parser.add_argument('--scale', type=int, default=10,
                                help='Pixel scale in meters (default: 10)')
    biweekly_parser.add_argument('--dtype', type=str, default='float32',
                                help='Data type for export (default: float32)')
    
    args = parser.parse_args()
    
    if args.command == 'monthly':
        # Validate month range
        if args.start_month > args.end_month:
            monthly_parser.error("start-month must be <= end-month")
        
        print(f"🚀 Starting monthly VC analysis for {args.year} (months {args.start_month}-{args.end_month})")
        print(f"📊 Output Mode: {args.output_mode.upper()}")
        
        result = month_VCpy(
            year=args.year,
            start_month=args.start_month,
            end_month=args.end_month,
            output_path=args.output_path,
            ndvi_threshold=args.ndvi_threshold,
            cloud_cover_max=args.cloud_cover_max,
            max_workers=args.max_workers,
            output_mode=args.output_mode,
            metro_asset=args.metro_asset,
            aoi_asset=args.aoi_asset,
            crs=args.crs,
            scale=args.scale,
            dtype=args.dtype
        )
        
        if result.get('success'):
            print(f"✅ Analysis completed successfully!")
            print(f"   Output: {result.get('output_path')}")
            print(f"   Months processed: {result.get('months_processed', 0)}")
            print(f"   Months with data: {result.get('months_with_data', 0)}")
            sys.exit(0)
        else:
            print(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    elif args.command == 'biweekly':
        # Validate month range
        if args.start_month > args.end_month:
            biweekly_parser.error("start-month must be <= end-month")
        
        print(f"🚀 Starting bi-weekly VC analysis for {args.year} (months {args.start_month}-{args.end_month})")
        print(f"📊 Output Mode: {args.output_mode.upper()}")
        print(f"📅 Acquisition Window: {args.acquisition_window} days")
        
        result = biweek_VCpy(
            year=args.year,
            start_month=args.start_month,
            end_month=args.end_month,
            output_path=args.output_path,
            ndvi_threshold=args.ndvi_threshold,
            cloud_cover_max=args.cloud_cover_max,
            acquisition_window=args.acquisition_window,
            max_workers=args.max_workers,
            output_mode=args.output_mode,
            metro_asset=args.metro_asset,
            crs=args.crs,
            scale=args.scale,
            dtype=args.dtype
        )
        
        if result.get('success'):
            print(f"✅ Analysis completed successfully!")
            print(f"   Output: {result.get('output_path')}")
            sys.exit(0)
        else:
            print(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()