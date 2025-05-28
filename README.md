# Copernicus Land Monitoring Service - NetCDF to COG conversion

This python script creates Cloud Optimized GeoTIFF image(s) based on the CLMS CF-1.6 compliant NetCDF products. The script requires an additional JSON file that describes the COG specific settings.

## Configuration file keys
The JSON configuration file should contain the following keys:
- (**tmpFolder**): (*string*) Optional path to folder to store temporary files created during COG generation. If omitted, the system default temp location will be used,
- **hasTimeIndex**: (*boolean*) Flag to indicate product name contains a time index (e.g. RT0 or SE1),
- **overwriteExistingFiles**: (*boolean*) Overwrite existing output files,
- **compressionMethod**: (*string*) compression method used, see gdal_translate for more information,
- **cogOverviews**: (*list of integers*) COG overview list, set None or empty list to skip overviews,
- **blockSize**: (*integer*) blockSize of COG overviews
- **attributeConversion**: (*dictionary*) NetCDF attributes to COG metadata conversion settings containing:
  - **history**: (*string*) string to be added to NetCDF history file attribute, can contain the replacement variable \<processDateISO\> and \<version\> who will be replaced by the date of processing and the version of the cogProcessor respectively.
  - **listEnclosure**: (*string*) unpack numeric list attributes into a string between the two elements. If an empty string is given, no enclosure is added,
  - **listSeparator**: (*string*) separated to be added to each numeric list element when converting to a string,
  - **removeAttributeLst**: (*list of strings*) attributes keys that will not be converted to metadata.
- **bandInfoList**: (*list of dictionaries*) A list of dictionaries (on for each band) that contains:
  - **inBand**: (*string*) band name of input file,
  - (**outBand**): (*string*) optional band id in output file, use empty string or False to use inBand name. If key is not present, the band will not be added to the base filename,
  - (**outBandType**): (*string*) optional band output type (use GDAL types),
  - **description**: (*string*) description to be added as band meta data to the COG,
  - **resampleMethod**: (*string*) resample method used for COG overviews, see gdaladdo for more information,
  - (**timeDimensionInfo**): (dictionary) optional, a dictionary to specify how to split multi-time dimension layers in the NetCDF file, containing:
    - **productTime**: (*string*) the corrected time element in the product date, expressed in <HHMM> format,
    - **timeBandIndexList**: (list of integers) the band indexes to group in a single COG,
    - **timeBandDescriptionList**: (list of strings) band description for each one of the multiple time bands in the COG. This description overrules the overall 'description' parameter in the bandInfoDict.

Two examples of configuration files are provided:
- ndvi_300m_v2_10daily.json
- lst-dc_5km_v2_10daily.json

## Requirements
This python script has been tested with python 3.8 and utilizes the gdal library to create the COG files from the NetCDF input. GDAL version 3.8.4 or higher and its python bindings need to be installed on the system that will execute the code. The script requires the following additional Python packages: numpy (1.24.4), cftime(1.6.3), certifi(2024.2.2) and NetCDF4(1.6.5). 

An example to setup the environment on AlmaLinux with Python 3.8 already installed, is provided below.
```
yum clean all; yum makecache; yum install -y python38-pip epel-release gcc-c++ gdal-3.8.4 gdal-devel-3.8.4 gdal-libs-3.8.4 python3-gdal-3.8.4 gdal-python-tools-3.8.4;
python3.8 -m pip install --upgrade pip; python3.8 -m pip install numpy==1.24.4 cftime==1.6.3 certifi==2024.2.2 NetCDF4==1.6.5
```

## Usage
```
pyton3.8 cogProcessor.py [-h] -c CFGFILE -i INFILE -o OUTFOLDER [-t TMPFOLDER]
                       [-l LOGFILE] [-q | -v]
arguments:
  -c CFGFILE, --cfgFile CFGFILE
                        JSON configuration file
  -i INFILE, --inFile INFILE
                        Full path to NetCDF input file
  -o OUTFOLDER, --outFolder OUTFOLDER
                        Full path to output folder in which the COGs will be stored
optional arguments:
  -h, --help            show this help message and exit
  -t TMPFOLDER, --tmpFolder TMPFOLDER
                        Optional full path to folder to store temporary files created during COG generation. Overrules the one specified in the configuration file. If no temp folder is provided, the system default folder will be used
  -l LOGFILE, --logFile LOGFILE
                        Optional log file
  -q, --quiet           Suppress output
  -v, --verbose         Verbose output
```
### Examples
Create COG files from a NDVI300 tile in the user's home directory under cog_output/ndvi_330m with verbose output
```
pyton3.8 cogProcessor.py -c example/ndvi/ndvi_300m_v2_10daily.json -i example/ndvi/c_gls_NDVI300_202505110000_X18Y03_OLCI_V2.0.1.nc -o ~/cog_output/ndvi300m -v
```
Create COG files from a online LST5KM Daily cycle in the user's home directory under cog_output/lst-dc_5km **and** with a logfile in the that output directory
```
pyton3.8 cogProcessor.py -c example/ndvi/lst-dc_5km_v2_10daily.json -i https://globalland.vito.be/download/netcdf/land_surface_temperature/lst_5km_v2_10daily-daily-cycle/2025/20250511/c_gls_LST10-DC_202505110000_GLOBE_GEO_V2.1.1.nc -o ~/cog_output/lst-dc_5km -l ~/cog_output/lst-dc_5km/conversion.log
```

