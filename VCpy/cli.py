"""
Command Line Interface for VCpy
"""

import argparse
import sys
from .biweekly import biweek_VCpy
from .monthly import month_VCpy

def run_biweekly():
    """Run bi-weekly VC analysis from command line"""
    parser = argparse.ArgumentParser(
        description='Run bi-weekly vegetation cover analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --year 2025 --months 6
  %(prog)s --year 2024 --months 12 --output-path /path/to/output
        """
    )
    
    parser.add_argument('--year', type=int, default=2025,
                       help='Year to process (default: 2025)')
    parser.add_argument('--months', type=int, default=12, choices=range(1, 13),
                       help='Number of months to process (1-12, default: 12)')
    parser.add_argument('--output-path', help='Custom output directory path')
    parser.add_argument('--ndvi-threshold', type=float, default=0.15,
                       help='NDVI threshold for vegetation cover (default: 0.15)')
    parser.add_argument('--cloud-cover-max', type=int, default=40,
                       help='Maximum cloud cover percentage (default: 40)')
    parser.add_argument('--export-ndvi', action='store_true',
                       help='Export NDVI images in addition to VC')
    
    args = parser.parse_args()
    
    print(f"🚀 Starting bi-weekly VC analysis for {args.year} ({args.months} months)")
    
    result = biweek_VCpy(
        year=args.year,
        months=args.months,
        output_path=args.output_path,
        ndvi_threshold=args.ndvi_threshold,
        cloud_cover_max=args.cloud_cover_max,
        export_ndvi=args.export_ndvi
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
  %(prog)s --year 2024 --output-path /path/to/output --export-ndvi
        """
    )
    
    parser.add_argument('--year', type=int, default=2025,
                       help='Year to process (default: 2025)')
    parser.add_argument('--start-month', type=int, default=1, choices=range(1, 13),
                       help='Starting month (1-12, default: 1)')
    parser.add_argument('--end-month', type=int, default=12, choices=range(1, 13),
                       help='Ending month (1-12, default: 12)')
    parser.add_argument('--export-ndvi', action='store_true',
                       help='Export NDVI images in addition to VC')
    parser.add_argument('--output-path', help='Custom output directory path')
    parser.add_argument('--ndvi-threshold', type=float, default=0.15,
                       help='NDVI threshold for vegetation cover (default: 0.15)')
    parser.add_argument('--cloud-cover-max', type=int, default=15,
                       help='Maximum cloud cover percentage (default: 15)')
    
    args = parser.parse_args()
    
    # Validate month range
    if args.start_month > args.end_month:
        parser.error("start-month must be <= end-month")
    
    print(f"🚀 Starting monthly VC analysis for {args.year} (months {args.start_month}-{args.end_month})")
    
    result = month_VCpy(
        year=args.year,
        start_month=args.start_month,
        end_month=args.end_month,
        output_path=args.output_path,
        ndvi_threshold=args.ndvi_threshold,
        cloud_cover_max=args.cloud_cover_max,
        export_ndvi=args.export_ndvi  # ADDED THIS LINE!
    )
    
    if result.get('success'):
        print(f"✅ Analysis completed successfully!")
        print(f"   Output: {result.get('output_path')}")
        sys.exit(0)
    else:
        print(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)

# For direct execution (optional)
if __name__ == "__main__":
    print("Use: vcpy-biweekly or vcpy-monthly from command line")
    print("Or import VCpy in Python scripts")