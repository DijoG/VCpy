from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="VCpy",
    version="0.1.0",
    author="DijoG",
    author_email="dijogergo@gmail.com",
    description="Vegetation Cover analysis using Google Earth Engine and Sentinel-2",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/DijoG/VCpy",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "earthengine-api>=0.1.0",
        "geedim>=0.1.0",
    ],
    entry_points={
        "console_scripts": [
            "vcpy-biweekly=VCpy.cli:run_biweekly",
            "vcpy-monthly=VCpy.cli:run_monthly",
        ],
    },
)