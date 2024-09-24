# -*- coding: utf-8 -*-
""" COG processing Kernel

Creates the global COG image(s) based on NetCDF input

The script requires an additional JSON file that describes the COG specific settings.

:author: Davy Wolfs <davy.wolfs@vito.be>

Notes
-----
Documented with Sphinx in numpy style:
 #. https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_numpy.html
 #. https://numpydoc.readthedocs.io/en/latest/format.html#docstring-standard
 
Parameters
----------
-c, --cfgFile : str
    Full path to json configuration file
-i, --inFile
    Full path to NetCDF input file
-o, --outFolder
    Full path to output folder in which the COG's will be stored
 
Returns
-------
int
    0: success
    1: error
 
Example
-------
The script can be called as follows:
    $ python cogProcessor.py --cfgFile ndvi300_v2_cog.json -i c_gls_NDVI300_202404010000_GLOBE_OLCI_V2.0.1.nc -o ~/cog/ndvi300_v2/
 
"""
__label__ = 'CLMS_NetCDF2COG'
__version__ = '1.0.0'
__date__ = '20240904'

# Regular imports
import os
import time 
import numpy
import shutil
import random
import subprocess
import netCDF4 as nc
from osgeo import gdal
from datetime import datetime
from time import strftime, strptime


def cogProcessor(cogCfgDict, logger = print):
    """COG processing kernel

    Creates the global COG image(s) from NetCDF input.
    For each band in the NetCDF input file that is also specified in the COG configuration
    dictionary, a COG file will be created in a temporary location based on executing a set of GDAL commands:
    * gdal_translate to convert a NetCDF band to a COG file
    * gdaladdo to add the overviews
    * gdal to add and/or alter file and band metadata
    * gdal_translate to create the final optimized output file
    Once finished, a safe copy is done to move the COG file to the final output location
    
    Parameters
    ----------
    cogCfgDict : dict
        configuration dictionary which should contain the following keys:
        * 'logFile': (str) Full path to log file. Set to None or false if no log file is required
        * 'tmpFolder': (str) Path to folder to store temporary files created during COG generation
        * 'outFolder':(str) Path to folder for COG output files
        * 'inFile': (str) Full path to NetCDF input file
        * 'hasTimeIndex': (bool) Flag to indicate product name contains a time index (e.g. RT0 or SE1)
        * 'overwriteExistingFiles': (bool) Overwrite existing output files
        * 'compressionMethod': (str) compression method used, see gdal_translate for more information
        * 'cogOverviews': (list of int) COG overview list, set None or empty list to skip overviews
        * 'blockSize': (int) blockSize of COG overviews
        * 'attributeConversion': (dict) NetCDF attributes to COG metadata conversion settings containing:
            * 'history': (str) string to be added to history, can contain the replacement variable <processDateISO> and <version>
            * 'listEnclosure': (str) unpack numeric list attributes into a string between the two elements. If an empty string is given, no enclosure is added.
            * 'listSeparator': (str) seprated to be added to each numeric list element when converting to a string
            * 'removeAttributeLst': (list of str) attributes keys that will not be converted to metadata
        * 'bandInfoList': (list of dict) A list of dictionaries (on for each band) that contains:
            * 'inBand': (str) band name of input file
            * 'outBand': (str) optional band id in output file, omit or None to use inBand
            * 'resampleMethod': (str) resample method used for COG overviews, see gdaladdo for more information
    logger : object
        Instance to log to, defaults to print
    """
    logger('COG Processing kernel')
    gdal.UseExceptions() # To prevent future warning

    # Create output folder
    logger(f' > Verifying output folder {cogCfgDict["outFolder"]}')
    if not os.path.isdir(cogCfgDict['outFolder']):
        _safeMakeDirs(cogCfgDict['outFolder'], mode=0o775)
        logger('   > Created')
    else:
        logger('   > Existing')

    # Create tmp folder
    logger(f' > Verifying temporary working folder {cogCfgDict["tmpFolder"]}')
    if not os.path.isdir(cogCfgDict['tmpFolder']):
        _safeMakeDirs(cogCfgDict['tmpFolder'], mode=0o775)
        logger('   > Created')
    else:
        logger('   > Existing')

    logger(f' > Extracting attributes from input file {cogCfgDict["inFile"]}')
    with nc.Dataset(cogCfgDict["inFile"], 'r') as src:
        attributeDict = src.__dict__
        bandLst = list(src.variables.keys())
        # check if the file has all bands to be converted
        for bandInfo in cogCfgDict['bandInfoList']:
            if bandInfo['inBand'] in bandLst:
                bandInfo['attributes'] = src.variables[bandInfo['inBand']].__dict__
            else:
                raise ValueError(f'{bandInfo["inBand"]} not found in {cogCfgDict["inFile"]}:{bandLst}')

    tempFileList = []
    logger(f' > Creating {len(cogCfgDict["bandInfoList"])} COG file(s)')
    for index, bandInfo in enumerate(cogCfgDict['bandInfoList']):
        srcPath = f'NETCDF:"{cogCfgDict["inFile"]}":{bandInfo["inBand"]}'

        cogFile = createCogFileName(os.path.basename(cogCfgDict['inFile']),
                                    bandInfo['inBand'],
                                    bandInfo['outBand'], 
                                    cogCfgDict['hasTimeIndex'])

        cogPath = os.path.join(cogCfgDict["outFolder"], cogFile)
        tempBasePath = os.path.join(cogCfgDict["tmpFolder"], os.path.splitext(cogFile)[0])
        logger(f'   > {index+1:>2}/{len(cogCfgDict["bandInfoList"])}: {cogFile}')
        if not cogCfgDict['overwriteExistingFiles'] and os.path.isfile(cogPath):
            logger('     > Skipped: file already exists')
            continue
        logger('     > Creating GeoTiff base image')
        tiffFile = tempBasePath + '_base.tiff'
        tempFileList.append(tiffFile)

        cmd = f'gdal_translate -of GTIFF {srcPath} {tiffFile}'

        logger(f'     > execute command: {cmd}')
        _runShellCmd(cmd, logger)

        if cogCfgDict["cogOverviews"]:
            logger('     > Adding overviews')
            cmd = f'gdaladdo -clean  {tiffFile}'
            logger(f'     > execute command: {cmd}')
            _runShellCmd(cmd, logger)
            overviewStr = map(str, cogCfgDict["cogOverviews"])
            overviewStr = ' '.join(overviewStr)
            cmd = f'gdaladdo -ro --config GDAL_TIFF_OVR_BLOCKSIZE {cogCfgDict["blockSize"]} --config COMPRESS_OVERVIEW {cogCfgDict["compressionMethod"]} -r {bandInfo["resampleMethod"]} {tiffFile} {overviewStr}'
            logger(f'     > execute command: {cmd}')
            _runShellCmd(cmd, logger)
            tempFileList.append(tiffFile+'.ovr')

        logger('     > Converting attributes to metadata')
        metadataDict = _convertFileAttributes(attributeDict, cogCfgDict['attributeConversion'], cogFile)
        bandMetadataDict = _convertBandAttributes(bandInfo['attributes'], cogCfgDict['attributeConversion'])

        logger('     > Setting metadata')
        ds = gdal.Open(tiffFile, gdal.GA_Update)
        ds.SetMetadata(metadataDict)
        ds.GetRasterBand(1).SetMetadata(bandMetadataDict)
        ds.GetRasterBand(1).SetDescription(bandInfo['description'])
        ds = None

        logger('     > Creating final COG')
        cogTmpFile = tempBasePath + '.tmp.tiff'
        cmd =  f'gdal_translate -of COG '
        cmd += f'-co COMPRESS={cogCfgDict["compressionMethod"]} '
        cmd += f'-co PREDICTOR=YES '
        cmd += f'--config GDAL_TIFF_OVR_BLOCKSIZE {cogCfgDict["blockSize"]} '
        cmd += f'{tiffFile} {cogTmpFile}'
        logger(f'     > execute command: {cmd}')
        _runShellCmd(cmd, logger)

        logger(f'     > Moving to final location: {cogPath}')
        _safeMove(cogTmpFile, cogPath)
        
    logger(f' > Removing temp files from {cogCfgDict["tmpFolder"]}')
    for tempFile in tempFileList:
        os.remove(tempFile)


def createCogFileName(inFile, inBand, outBand = None, hasTimeIndex = False):
    """ Create the cog output filename.
    
    Band name conversions is done when outBand is set.
    Band name is appended to the end of the product name, unless hasTimeIndex is 
    True, then the time index is the latest component.
    
    Parameters
    ----------
    inFile : str
        Base file name of NetCDF input file
    inBand : str
        Band name of the input file
    outBand : str
        Band name in the output file, can be used to a name conversion. When 
        empty or None, inBand is used. Defaults to None
    hasTimeIndex : bool
        Indicates the filename has a time index. Band name is appended to the 
        end of the product name, unless hasTimeIndex is True, then the time 
        index is the latest component. Defaults to False
    
    Returns
    -------
    str
        CGLS compatible COG output file name
    """
    prodElements = _unpackNetCDFProductName(inFile, hasTimeIndex)
    if outBand:
        prodElements['parameter'] = outBand
    else:
        prodElements['parameter'] = inBand
    cogFile = _packCOGProductName(prodElements)
    return cogFile


def _safeMakeDirs(directory, mode=0o777, attempts = 3):
    """ create a directory on the cluster, safeguarding multiple servers doing the same
    
    Parameters
    ----------
    directory : str
        Directory path to create, allowing recursive structure to be created
    mode : int
        Integer value representing mode of the newly created directory
    attempts : int
        Number of attempts before raising the latest exception
    
    Returns
    -------
    None
    """
    while True:
        try:
            os.makedirs(directory, mode=mode, exist_ok=True)
            break
        except:
            if attempts == 1:
                raise
            time.sleep(random.uniform(0.1,5.0))
            if os.path.isdir(directory):
                 break
            attempts -= 1


def _today(outFormat='%Y-%m-%d'):
    """Get the system date in the desired format

    Parameters
    ----------
    outFormat: str, optional
        String representation of returned date, defaults to ISO '%Y-%m-%d'

    Returns
    -------
    str
        date

    """
    timestampFormat = '%Y-%m-%d %H:%M:%S.%f'
    timestamp = datetime.now().strftime(timestampFormat)
    date=strptime(timestamp,timestampFormat)
    return strftime(outFormat,date)


def _convertFileAttributes(attributeDict, conversionDict, filename):
    """ Convert CF-1.6 NetCDF file attributes to COG metadata

    Parameters
    ----------
    attributeDict : dict
        NetCDF CF-1.6 attributes
    conversionDict : dict
        Conversion settings
    filename : str
        COG filename
    
    Returns
    -------
    Dict:
        COG metadata
    """
    metadata = {}
    for key, value in attributeDict.items():
        if key in conversionDict['removeAttributeLst']:
            continue
        if key == 'history':
            history = conversionDict['history']
            history = history.replace('<processDateISO>', _today())
            history = history.replace('<version>', __version__)
            metadata[key] = value + f'\n{history}'
        elif key == 'identifier':
            id = os.path.splitext(filename)[0]
            id = id.replace('c_gls_', '')
            metadata[key] = f'{attributeDict["parent_identifier"]}:{id}'
        else:
            metadata[key] = value
    return metadata


def _convertBandAttributes(attributeDict, conversionDict):
    """ Convert CF-1.6 NetCDF band attributes to COG metadata

    Parameters
    ----------
    attributeDict : dict
        NetCDF CF-1.6 attributes
    conversionDict : dict
        Conversion settings
    
    Returns
    -------
    Dict:
        COG band metadata
    """
    metadata = {}
    for key, value in attributeDict.items():
        if key in conversionDict['removeAttributeLst']:
            continue
        elif type(value) == numpy.ndarray:
            lstStr = conversionDict['listSeparator'].join(map(str, value))
            if len(conversionDict['listEnclosure']) == 2:
                lstStr = f'{conversionDict["listEnclosure"][0]}{lstStr}{conversionDict["listEnclosure"][1]}'
            elif len(conversionDict['listEnclosure']) != 0:
                raise ValueError('Attribute conversion parameter listEnclosure must be either two or none characters')
            metadata[key] = lstStr
        else:
            metadata[key] = value
    return metadata


def _runShellCmd(cmd, logger):
    """ run a command (cmd) with subprocess and put ouput in logger
    
    Parameters
    ----------
    cmd : str
    logger : object
        Instance to log to
    
    Returns
    -------
    None
    """
    try:
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        logger('     Failed!')
        logger('     Process output:')
        logger('     +-')
        for line in e.output.splitlines():
            logger('     | ' + line.decode('utf-8'))
        logger('     +-')
        raise e

    logger('     Done.')
    logger('     Process output:')
    logger('     +-')
    for line in output.splitlines():
        logger('     | ' + line.decode('utf-8'))
    logger('     +-')


def _unpackNetCDFProductName(productname, hasTimeIndex):
    """ Unpack CGLOPS NetCDF product name into dictionary of elements
    <project>_<product>_<productDate>_<ROI>_<SENSOR>_<VERSION>.nc
    c_gls_NDVI300_202404010000_AFRI_OLCI_V2.0.1.nc
    c_gls_FAPAR300-RT0_202404100000_GLOBE_OLCI_V1.1.2
    Parameters
    ----------
    productname : str
        CGLOPS product name
    hasTimeIndex : bool
        Indicates the filename has a time index.
    
    Returns
    -------
    Dict:
        CGLOPS product name elements
    """
    _filename, _file_ext = os.path.splitext(productname)
    parts = _filename.split('_')
    productParts = parts[2].split('-')
    prodDict = {
        'project':     '_'.join(parts[0:2]),
        'product':     productParts[0],
        'productDate': parts[3],
        'roi':         parts[4],
        'sensor':      parts[5],
        'version':     parts[6],
        'extention':   _file_ext
        }
    if len(productParts) == 1 and not hasTimeIndex:
        prodDict['subProduct'] = None
        prodDict['timeIndex']  = None
    elif len(productParts) == 2:
        if hasTimeIndex:
            prodDict['subProduct'] = None
            prodDict['timeIndex']  = productParts[1]
        else:
            prodDict['subProduct'] = productParts[1]
            prodDict['timeIndex']  = None
    elif len(productParts) == 3 and hasTimeIndex:
        prodDict['subProduct'] = productParts[1]
        prodDict['timeIndex']  = productParts[2]
    else:
        raise ValueError(f'Incompatible combination of product ({parts[2]}) and time index ({hasTimeIndex})')
    return prodDict


def _packCOGProductName(prodElements):
    """ pack dictionary of elements into official CGLOPS COG product name 
    Parameters
    ----------
    prodElements: Dict
        CGLOPS product name elements
    
    Returns
    -------
    str
        CGLOPS product name
    """
    if prodElements["subProduct"]:
        productTag = f'{prodElements["product"]}-{prodElements["subProduct"]}-{prodElements["parameter"]}'
    else:
        productTag = f'{prodElements["product"]}-{prodElements["parameter"]}'
    if prodElements["timeIndex"]:
        productTag = f'{productTag}-{prodElements["timeIndex"]}'
    return f'{prodElements["project"]}_{productTag}_{prodElements["productDate"]}_{prodElements["roi"]}_{prodElements["sensor"]}_{prodElements["version"]}.tiff'


def _safeMove(src, dst, mod = 0o644):
    """ Do a 'save' move from source (src) to destination (dst)

    A 'save' move will first copy a temporary file to the destination and then
    rename the temporary file to the destination file. If files already exists,
    they will be removed before the copy/rename action. In all is succesfull, the src
    file will be removed.

    Parameters
    ----------
    src: str
        The source file
    dst: str
        The destination file
    mod: str
        File permisions (octal), defaults to owner R/W, group R, others R
    """
    tmpFile = dst + '.temp'
    if os.path.isfile(tmpFile):
        os.remove(tmpFile)
    shutil.copy(src, tmpFile)
    if os.path.isfile(dst):
        os.remove(dst)
    os.rename(tmpFile, dst)
    os.chmod(dst, mod)
    os.remove(src)


# --- Python main entry --------------------------------------------------------
if __name__ == '__main__':
    """ Imports that are only relevant in stand alone """
    import sys
    import json
    import logging
    import argparse
    import traceback
    from time import time, gmtime
    
    """ Ancillary functions that are only relevant to stand alone """
    def _getLogger(logName, logFile=None, consoleLogLevel=logging.INFO):
        """Create a logger instance
        
        stdout will be logged till consoleLogLevel, default INFO level
        logfile will be logged till DEBUG level
    
        Parameters
        ----------
        logName : str
            Name of the logger instance
        logFile : str
            Optional: Path the file in which all will be logged
        consoleLogLevel : logging.LEVEL
            Optional: Loglevel for stdout, default to info
        
        Returns
        -------
        logger:
            A logger instance
        """
        logger = logging.getLogger(logName)
        logger.setLevel(logging.DEBUG)

        if logFile:
            fileHandler = logging.FileHandler(logFile)
            fileHandler.setLevel(logging.DEBUG)
            fileFormatter = logging.Formatter(
                '%(asctime)s.%(msecs)-3d %(levelname)-8s ' \
                '[%(module)12s:%(lineno)-3d] %(message)s',
                '%Y.%m.%d %H:%M:%S')
            fileHandler.setFormatter(fileFormatter)
            logger.addHandler(fileHandler)

        consoleHandler = logging.StreamHandler()
        consoleHandler.setLevel(consoleLogLevel)
        consoleFormatter = logging.Formatter(
            '%(levelname)-8s %(message)s',
            '')
        consoleHandler.setFormatter(consoleFormatter)
        logger.addHandler(consoleHandler)

        return logger


    parser = argparse.ArgumentParser(prog='cogProcessor.py',
                                     description = 'COG creation from NetCDF input file')
    parser.add_argument('-c', '--cfgFile', type=str, required = True, 
                        help='JSON configuration file')
    parser.add_argument('-i', '--inFile', type=str, required=True,
                        help='Full path to NetCDF input file')
    parser.add_argument('-o', '--outFolder', type=str, required=True,
                        help='Full path to output folder in which the COGs will be stored')
    parser.add_argument('-t', '--tmpFolder', type=str, required=False, default=None,
                        help='Optional full path to folder to store temporary files created during COG generation. Overrules the one specified in the configuration file')
    parser.add_argument('-l', '--logFile', type=str, required=False, default=None,
                        help='Optional log file, overrules the one specified in the configuration file')
    modeGrp = parser.add_mutually_exclusive_group()
    modeGrp.add_argument('-q', '--quiet', action='store_true', help='Suppress output')
    modeGrp.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    # Create the configuration dictionary based on the configuration file and the date input
    with open(args.cfgFile, 'r') as cfgFile:
        cfgDict = json.load(cfgFile)
    cfgDict['inFile'] = args.inFile
    cfgDict['outFolder'] = args.outFolder

    if args.logFile:
        cfgDict['logFile'] = args.logFile

    # setup logger
    if cfgDict['logFile']:
        # Create log folder if non-existing
        logFolder = os.path.dirname(cfgDict['logFile'])
        if not os.path.isdir(logFolder):
            os.makedirs(logFolder, exist_ok=True)
    if args.quiet:
        consoLogLevel = logging.WARNING
    elif args.verbose:
        consoLogLevel = logging.DEBUG
    else:
        consoLogLevel = logging.INFO
    logger = _getLogger('COG Processor', cfgDict['logFile'], consoLogLevel)
    if cfgDict['logFile']:
        logger.info(f'Logfile: {cfgDict["logFile"]}')
    # Test if the configuration dictionary is in a valid format
    logger.debug(json.dumps(cfgDict))

    if args.tmpFolder:
        cfgDict['tmpFolder'] = args.tmpFolder
    try:
        logger.info(f'Processing {os.path.basename(cfgDict["inFile"])}')
        startTime = time()
        cogProcessor(cfgDict, logger.debug)
        endTime = time()
        logger.info(f'Ended processing in {strftime("%H:%M:%S", gmtime(endTime - startTime))}')

    except:
        traceback.print_exc()
        sys.exit(1)
    sys.exit(0)
