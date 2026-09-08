"""
VCpy - Vegetation Cover Python Package for Earth Engine Image Acquisition

This package provides functions for bi-weekly and monthly vegetation cover analysis
using Google Earth Engine and Sentinel-2 imagery.

Main functions:
    biweek_VCpy() - Bi-weekly vegetation cover analysis
    month_VCpy() - Monthly vegetation cover analysis
"""

from .biweekly import biweek_VCpy
from .monthly import month_VCpy
from .config import DEFAULT_CONFIG

__version__ = "1.0.0"
__all__ = ['biweek_VCpy', 'month_VCpy', 'DEFAULT_CONFIG']