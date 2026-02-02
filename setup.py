from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="VCpy",
    version="1.0.0",
    author="Gergo Dioszegi",
    author_email="dijogergo@gmail.com",
    description="Vegetation Cover analysis with Google Earth Engine for bi-weekly and monthly data acquisition",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/DijoG/VCpy",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: GIS",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "earthengine-api>=0.1.367",
        "geedim>=1.7.2",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "vcpy-biweekly=VCpy.cli:run_biweekly",
            "vcpy-monthly=VCpy.cli:run_monthly",
        ],
    },
    license="MIT",
    keywords="google-earth-engine vegetation-cover ndvi remote-sensing sentinel-2 gis",
)