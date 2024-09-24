# Copernicus Land Monitoring Service - NetCDF to COG conversion

This python script creates Cloud Optimized GeoTIFF image(s) based on the CLMS CF-1.6 compliant NetCDF products. The script requires an additional JSON file that describes the COG specific settings.

## Configuration file keys
The JSON configuration file should contain the following keys:
- **logFile**: (*string*) Full path to log file. Set to None or false if no log file is required,
- **tmpFolder**: (*string*) Path to folder to store temporary files created during COG generation,
- **outFolder**:(*string*) Path to folder for COG output files,
- **inFile**: (*string*) Full path to NetCDF input file,
- **hasTimeIndex**: (*boolean*) Flag to indicate product name contains a time index (e.g. RT0 or SE1),
- **overwriteExistingFiles**: (*boolean*) Overwrite existing output files,
- **compressionMethod**: (*string*) compression method used, see gdal_translate for more information,
- **cogOverviews**: (*list of integers*) COG overview list, set None or empty list to skip overviews,
- **blockSize**: (*integer*) blockSize of COG overviews
- **attributeConversion**: (*dictionary*) NetCDF attributes to COG metadata conversion settings containing:
  - **history**: (*string*) string to be added to NetCDF history file attribute, can contain the replacement variable \<processDateISO\> and \<version\> who will be replaced by the date of processing and the version of the cogProcessor respectively.
  - **listEnclosure**: (*string*) unpack numeric list attributes into a string between the two elements. If an empty string is given, no enclosure is added,
  - **listSeparator**: (*string*) seprated to be added to each numeric list element when converting to a string,
  - **removeAttributeLst**: (*list of strings*) attributes keys that will not be converted to metadata.
- **bandInfoList**: (*list of dictionaries*) A list of dictionaries (on for each band) that contains:
  - **inBand**: (*string*) band name of input file,
  - **outBand**: (*string*) optional band id in output file, omit or None to use inBand,
  - **description**: (*string*) description to be added as band meta data to the COG,
  - **resampleMethod**: (*string*) resample method used for COG overviews, see gdaladdo for more information.

The configuration for the ndvi300 v2 ten daily product is provided as an example.

## Requirements
This python script has been tested with python 3.8 and utilises the gdal library to create the COG files from the NetCDF input. GDAL version 3.8.4 or higher and its python bindings need to be installed on the system that will execute the code. The script requires the following additional Python packages: numpy (1.24.4), cftime(1.6.3), certifi(2024.2.2) and NetCDF4(1.6.5). 

An example to setup the environment on AlmaLinux with Python 3.8 already installed, is provided below.
```
yum clean all; yum makecache; yum install -y python38-pip epel-release gcc-c++ gdal-3.8.4 gdal-devel-3.8.4 gdal-libs-3.8.4 python3-gdal-3.8.4 gdal-python-tools-3.8.4;
python3.8 -m pip install --upgrade pip; python3.8 -m pip install numpy==1.24.4 cftime==1.6.3 certifi==2024.2.2 NetCDF4==1.6.5
```

## Usage
```
pyton3.8  cogProcessor.py [-h] -c CFGFILE -i INFILE -o OUTFOLDER [-t TMPFOLDER]
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
                        Optional full path to folder to store temporary files created during COG generation. Overrules the one specified in the configuration file
  -l LOGFILE, --logFile LOGFILE
                        Optional log file, overrules the one specified in the configuration file
  -q, --quiet           Suppress output
  -v, --verbose         Verbose output
```
