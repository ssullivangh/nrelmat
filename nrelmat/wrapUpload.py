#!/bin/env python
# Copyright 2013 National Renewable Energy Laboratory, Golden CO, USA
# This file is part of NREL MatDB.
#
# NREL MatDB is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# NREL MatDB is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with NREL MatDB.  If not, see <http://www.gnu.org/licenses/>.

import datetime, json, math, os, pexpect, pwd, re
import shutil, socket, stat, subprocess, sys, time, traceback


# Name of the metadata file
metadataName = 'metadata'


# Names of required files
requireNames = [
  metadataName,
  'INCAR',
  'KPOINTS',
  'POSCAR',
  'POTCAR',
  'OUTCAR',
  'vasprun.xml',
]

# Names of optional files
optionNames = [
  'pbserr',
  'pbsout',
  'pbsscript',
  'stderr',
  'stdout',
  'DOSCAR',
]


# Work and archive subdir of the top level dir.
digestDirName = 'wrapUpload.archive'

# Name of smallMap json file within each archived dir
smallMapFile = 'wrapUpload.json'

#====================================================================

def badparms( msg):
  print '\nError: %s' % (msg,)
  print 'Parms:'
  print ''
  print '  -bugLev     <int>       Debug level.  Default: 0'
  print ''
  print '  -metadataSpec <string>  Metadata file to be forced on all.'
  print ''
  print '  -keepList   <string>    File containing the absolute paths'
  print '                          of the dirs to be uploaded.'
  print '                          Still topDir must be specified,'
  print '                          and all paths in keepList must'
  print '                          start with the specified topDir.'
  print '                          If keepList is specified,'
  print '                          keepPatterns and omitPatterns'
  print '                          must not be specified.'
  print ''
  print '  -keepPatterns           Comma separated list of'
  print '                          regular expressions matching'
  print '                          the relative paths of those directories'
  print '                          to be kept.  If specified,'
  print '                          keepList must not be specified.'
  print ''
  print '  -omitPatterns           Comma separated list of'
  print '                          regular expressions matching'
  print '                          the relative paths of those directories'
  print '                          to be omitted.  If specified,'
  print '                          keepList must not be specified.'
  print ''
  print '  -topDir     <string>    Top of dir tree to upload.'
  print ''
  print '  -workDir    <string>    Work dir'
  print ''
  print '  -serverInfo <string>    JSON file containing info about the server'
  sys.exit(1)


#====================================================================


def main():
  '''
  Locates model runs, checks and extracts dir contents,
  and uses ``tar`` and ``scp`` to send the data to the server running
  :mod:`wrapReceive`.

  Command line parameters:

  =================   =========    ===========================================
  Parameter           Type         Description
  =================   =========    ===========================================
  **-bugLev**         integer      Debug level.  Normally 0.

  **-metadataSpec**   string       Metadata file to be forced on all.
                                   If specified, the metadata files found
                                   in the archived dirs are ignored,
                                   and the ``metadataSpec`` file
                                   is used instead.
                                   Default: None, meaning each archived
                                   dir must contain a metadata file.

  **-keepList**       string       File containing the absolute paths
                                   of the dirs to be uploaded.
                                   Still ``topDir`` must be specified,
                                   and all paths in ``keepList`` must
                                   start with the specified ``topDir``.
                                   If ``keepList`` is specified,
                                   ``keepPatterns`` and ``omitPatterns``
                                   must not be specified.
        
  **-keepPatterns**   string       Comma separated list of
                                   regular expressions matching
                                   the relative paths of those directories
                                   to be kept.  If specified,
                                   ``keepList`` must not be specified.
        
  **-omitPatterns**   string       Comma separated list of
                                   regular expressions matching
                                   the relative paths of those directories
                                   to be omitted.  If specified,
                                   ``keepList`` must not be specified.
        
  **-topDir**         string       Top of dir tree to upload.
        
  **-workDir**        string       Work dir

  **-serverInfo**     string       JSON file containing info about the server.
                                   The following keys must be defined:

                                     =============   =========================
                                     Key             Value
                                     =============   =========================
                                     hostname        host where wrapReceive.py
                                                     is running
                                     userid          account for wrapReceive
                                     password        password for wrapReceive
                                     dir             incoming dir for
                                                     wrapReceive
                                     =============   =========================
  =================   =========    ===========================================
  '''


  bugLev = 0
  func = 'upload'
  metadataSpec = None
  requireIcsd = None
  keepList = None
  keepPatterns = None
  omitPatterns = None
  topDir = None
  workDir = None
  serverInfo = None

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if   key == '-bugLev': bugLev = int( val)
    elif key == '-func': func = val
    elif key == '-metadataSpec': metadataSpec = val
    elif key == '-requireIcsd': requireIcsd = parseBoolean( val)
    elif key == '-keepList': keepList = val
    elif key == '-keepPatterns': keepPatterns = val.split(',')
    elif key == '-omitPatterns': omitPatterns = val.split(',')
    elif key == '-topDir': topDir = val
    elif key == '-workDir': workDir = val
    elif key == '-serverInfo': serverInfo = val
    else: badparms('unknown key: "%s"' % (key,))

  # func is optional
  # metadataSpec is optional
  if requireIcsd == None: badparms('missing parameter: -requireIcsd')
  # keepList is optional
  # keepPatterns is optional
  # omitPatterns is optional
  if keepList != None and (keepPatterns != None or omitPatterns != None):
    badparms('with keepList, may not spec keepPatterns or omitPatterns')
  if topDir == None: badparms('missing parameter: -topDir')
  if workDir == None: badparms('missing parameter: -workDir')
  if serverInfo == None: badparms('missing parameter: -serverInfo')
  absTopDir = os.path.abspath( topDir)

  print 'wrapUpload: func: %s' % (func,)
  print 'wrapUpload: metadataSpec: %s' % (metadataSpec,)
  print 'wrapUpload: keepList: %s' % (keepList,)
  print 'wrapUpload: keepPatterns: %s' % (keepPatterns,)
  print 'wrapUpload: omitPatterns: %s' % (omitPatterns,)
  print 'wrapUpload: topDir: %s' % (topDir,)
  print 'wrapUpload: absTopDir: %s' % (absTopDir,)
  print 'wrapUpload: workDir: %s' % (workDir,)
  print 'wrapUpload: serverInfo: %s' % (serverInfo,)

  if func == 'upload':
    doUpload( bugLev, metadataSpec, requireIcsd,
      keepList, keepPatterns, omitPatterns,
      topDir, workDir, serverInfo)

  elif func == 'testMetadata':
    metadata = parseMetadata( metadataSpec)
    printMap( 'metadata', metadata, 10000)

  else: badparms('unknown func: %s' % (func,))


#====================================================================


def doUpload(
  bugLev,
  metadataSpec,
  requireIcsd,                # require icsd info in absTopDir string
  keepList,
  keepPatterns,
  omitPatterns,
  topDir,
  workDir,
  serverInfo):
  '''
  Locates model runs, checks and extracts dir contents,
  and uses ``tar`` and ``scp`` to send the data to the server running
  :mod:`wrapReceive`.

  If ``keepList`` is specified, creates keepAbsPaths = unique absolute
  paths and calls :func:`iterateDirs`.

  Otherwise calls :func:`searchDirs` to recursively search the
  directory tree starting at ``topDir``.

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.

  * metadataSpec (str):
    Metadata file to be forced on all.
    If specified, the metadata files found
    in the archived dirs are ignored,
    and the ``metadataSpec`` file
    is used instead.
    Default: None, meaning each archived
    dir must contain a metadata file.

  * requireIcsd (boolean): if True, the absTopDir string must
    contain ICSD info that :func:`getIcsdMap` can extract.

  * keepList (str[]):
    List of the absolute paths
    of the dirs to be uploaded, or None.
    Still ``topDir`` must be specified,
    and all paths in ``keepList`` must
    start with the specified ``topDir``.
    If ``keepList`` is specified,
    ``keepPatterns`` and ``omitPatterns``
    must not be specified.
        
  * keepPatterns (str[]):
    List of regular expressions matching
    the relative paths of those directories
    to be kept.  If specified,
    ``keepList`` must not be specified.
        
  * omitPatterns (str[]):
    List of regular expressions matching
    the relative paths of those directories
    to be omitted.  If specified,
    ``keepList`` must not be specified.
        
  * topDir (str):       Top of dir tree to upload.
        
  * workDir (str):      Work dir

  * serverInfo (str):   JSON file containing info about the server

  **Returns**

  * None

  '''

  with open( serverInfo) as fin:
    serverMap = json.load( fin)
  for key in ['hostname', 'userid', 'password', 'dir']:
    if not serverMap.has_key( key):
      throwerr('serverInfo is missing key: %s' % (key,))

  absTopDir = os.path.abspath( topDir)
  metadataForce = None
  if metadataSpec != None:
    metadataForce = parseMetadata( metadataSpec)

  # Get keepAbsPaths from file keepList
  # Use a set and os.path.abspath to make sure entries are unique.
  keepAbsPaths = None
  if keepList != None:
    keepAbsPathSet = set()
    with open( keepList) as fin:
      iline = 0
      while True:
        line = fin.readline()
        if line == '': break
        iline += 1
        line = line.strip()
        if len(line) > 0 and not line.startswith('#'):
          if not line.startswith('/'):
            throwerr('keepList line is not an abs path.  iline: %d  line: %s' \
              % (iline, line,))

          apath = os.path.abspath( line)
          if not apath.startswith( absTopDir):
            throwerr('keepList line not under topDir.  iline: %d  line: %s' \
              % (iline, line,))
          if not os.path.isdir( apath):
            throwerr('keepList line is not a dir.  iline: %d  line: %s' \
              % (iline, line,))
          keepAbsPathSet.add( apath)
    keepAbsPaths = list( keepAbsPathSet)
    keepAbsPaths.sort()

  digestDir = os.path.join( workDir, digestDirName)

  if os.path.lexists( digestDir):
    throwerr('workDir is not empty: subdir already exists: %s' \
      % (digestDir,))

  # Recursively get "stat" info (filename, len, dates)
  # for a directory tree.  Uses absolute paths.
  statInfos = []
  getStatInfos( bugLev, absTopDir, statInfos)

  # Init miscMap
  curDate = datetime.datetime.now()
  userId = pwd.getpwuid(os.getuid())[0]
  hostName = socket.gethostname()
  miscMap = {
    'numWarn': 0,
    'curDate': curDate.strftime('%Y-%m-%dT%H:%M:%S.%f'),
    'userId': userId,
    'hostName': hostName,
  }

  # Create countMap
  countMap = {}
  for nm in requireNames + optionNames:
    count = findNumFiles( nm, absTopDir)
    countMap[nm] = count
    if bugLev >= 5:
      print 'wrapUpload: tag: %s  total count: %d' % (nm, count,)

  relDirs = []           # parallel: list of dirs we archive
  dirMaps = []           # parallel: list of dir info maps
  icsdMaps = []          # parallel: list of icsd info maps
  relFiles = []          # list of files to archive

  if keepAbsPaths != None:
    # Get the relative paths of all files to be archived,
    # using the keepAbsPaths list.
    iterateDirs(
      bugLev,
      keepAbsPaths,
      absTopDir,
      metadataForce,              # metadata to force on all dirs
      requireIcsd,                # require icsd info in absTopDir string
      miscMap,                    # appends to map
      relDirs,                    # parallel: appends to list
      dirMaps,                    # parallel: appends to list
      icsdMaps,                   # parallel: appends to list
      relFiles)                   # appends to list


  else:
    # Get the relative paths of all files to be archived,
    # starting at absTopDir.
    searchDirs(
      bugLev,
      keepPatterns,
      omitPatterns,
      absTopDir,
      '',                         # relative path so far
      metadataForce,              # metadata to force on all dirs
      requireIcsd,                # require icsd info in absTopDir string
      miscMap,                    # appends to map
      relDirs,                    # parallel: appends to list
      dirMaps,                    # parallel: appends to list
      icsdMaps,                   # parallel: appends to list
      relFiles)                   # appends to list

  numKeptDir = len( relDirs)
  if bugLev >= 1:
    print 'wrapUpload: numKeptDir: %d', (numKeptDir,)
    printMap('wrapUpload: miscMap:', miscMap, 100)

  os.mkdir( digestDir)

  # Write JSON
  # First delete the env vars that aren't serializable
  envMap = os.environ.copy()
  for key in envMap.keys():
    isOk = True
    try:
      json.dumps( key)
      json.dumps( envMap[key])
    except TypeError, exc:
      if bugLev >= 5: print 'cannot serialize env key: "%s"' % (key,)
      del envMap[key]

  numWarn = miscMap['numWarn']
  if numWarn > 0:
    throwerr('\nFound %d warnings.  See notes above' % (numWarn,))

  # Print statistics
  msg = 'wrapUpload: file summary:\n'
  for nm in requireNames:
    totNum = countMap[nm]
    msg += '  Total num %-12s files found: %4d    Kept: %4d  Omitted: %4d\n' \
      % (nm, totNum, numKeptDir, totNum - numKeptDir,)
  logit( msg)

  # Coord with fillDbVasp.py fillTable
  overMap = {
    'miscMap': miscMap,
    'countMap': countMap,
    'envMap': envMap,
    'statInfos': statInfos,
    'topDir': absTopDir,
    'numKeptDir': numKeptDir,
    'relDirs': relDirs,
    'dirMaps': dirMaps,
    'icsdMaps': icsdMaps,
    'relFiles': relFiles,
    'metadataForce': metadataForce,
  }
  if bugLev >= 1:
    printMap('wrapUpload: overMap:', overMap, 100)

  listFile = os.path.join( digestDir, 'digest.list')
  with open( listFile, 'w') as fout:
    for path in relFiles:
      print >> fout, path

  logit('wrapUpload: beginning tar (this could take several minutes)')
  uui = formatUui( curDate, userId, absTopDir)
  fBase = os.path.join( digestDir, uui)

  overFile = fBase + '.json'
  tarFile = fBase + '.tgz' 
  flagFile = fBase + '.flag' 

  # Write JSON to overFile
  with open( overFile, 'w') as fout:
    json.dump( overMap, fout, sort_keys=True, indent=2,
      separators=(',', ': '))

  # Create tarFile = tar of the files to be saved.
  args = ['/bin/tar', '-czf', tarFile, '-T', listFile, '--mode=660']
  runSubprocess( bugLev, absTopDir, args, False)  # showStdout = False

  # Create empty flagFile
  with open( flagFile, 'w') as fout:
    pass   # just create the file

  # Use scp to upload overFile, tarFile, flagFile.

  args = ['chmod', '660', tarFile, flagFile]
  runSubprocess( bugLev, os.getcwd(), args, False)  # showStdout = False

  logit('wrapUpload: beginning scp (this could take several minutes)')

  cmdLine = '/usr/bin/scp -v -p %s %s %s %s@%s:%s' \
    % (overFile,
    tarFile,
    flagFile,             # flagFile must be last for wrapReceive.py
    serverMap['userid'],
    serverMap['hostname'],
    serverMap['dir'])
  if bugLev >= 1:
    print 'wrapUpload: scp cmdLine: %s' % (cmdLine)

  proc = pexpect.spawn( cmdLine)
  proc.expect(' password: ')
  proc.sendline( serverMap['password'])
  proc.expect( pexpect.EOF)

  logit('wrapUpload: Completed upload of %d directories.' % (numKeptDir,))


#====================================================================


def searchDirs(
  bugLev,
  keepPatterns,
  omitPatterns,
  absTopDir,
  relPath,                    # relative path so far
  metadataForce,              # metadata to force on all dirs
  requireIcsd,                # require icsd info in absTopDir string
  miscMap,                    # appends to map
  relDirs,                    # parallel: appends to list
  dirMaps,                    # parallel: appends to list
  icsdMaps,                   # parallel: appends to list
  relFiles):                  # appends to list
  '''
  Recursive: locates model runs, checks dir contents,
  and appends names to lists of dirs and files.

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.

  * keepPatterns (str[]):
    List of regular expressions matching
    the relative paths of those directories
    to be kept.  If specified,
    ``keepList`` must not be specified.
        
  * omitPatterns (str[]):
    List of regular expressions matching
    the relative paths of those directories
    to be omitted.  If specified,
    ``keepList`` must not be specified.

  * absTopDir (str): Absolute path of the original top of dir tree to upload.
        
  * relPath (str): Relative path so far, somewhere below absTopDir.
        
  * metadataForce (map):
    Metadata map to be forced on all.
    If specified, the metadata files found
    in the archived dirs are ignored.
    Default: None, meaning each archived
    dir must contain a metadata file.

  * requireIcsd (boolean): if True, the absTopDir string must
    contain ICSD info that :func:`getIcsdMap` can extract.

  * miscMap (map): we call :func:`processDir`, which may increment
    miscMap['numWarn'].

  * relDirs (str[]): we append dir names to this list.

  * dirMaps (map[]): we append maps to this list.
    Parallel with relDirs.

  * icsdMaps (map[]): we append maps (from :func:`getIcsdMap`)
    to this list.
    Parallel with relDirs.

  * relFiles (str[]): We append file names to be archived.

  **Returns**

  * None
  '''

  inDir = os.path.abspath( os.path.join( absTopDir, relPath))
  if bugLev >= 5:
    print 'searchDirs: relPath: %s' % (relPath,)
    print 'searchDirs: inDir: %s' % (inDir,)
  if not os.path.isdir( inDir): throwerr('not a dir')

  # Check for keepPattern and omitPattern matches.
  # If any keepPatterns exist:
  #   keepIt = (not any omitPattern) and some keepPattern
  # Else:
  #   keepIt = not any omitPattern

  keepIt = True
  if keepPatterns != None:
    found = False
    for pat in keepPatterns:
      if re.search( pat, relPath):
        if bugLev >= 5:
          print 'searchDirs: match keepPattern: %s  for relPath: %s' \
            % (pat, relPath,)
        found = True
        break
    if not found: keepIt = False

  omitIt = False
  if omitPatterns != None:
    for pat in omitPatterns:
      if re.search( pat, relPath):
        if bugLev >= 5:
          print 'searchDirs: match omitPattern: %s  for relPath: %s' \
            % (pat, relPath,)
        omitIt = True

  hasMetadata = False
  if metadataForce == None:
    mpath = os.path.join( inDir, metadataName)
    if os.path.isfile( mpath):
      parseMetadata( mpath)        # check validity
      hasMetadata = True
  else: hasMetadata = True

  if bugLev >= 5:
    print 'searchDirs: keepIt: %s  omitIt: %s  hasMetadata: %s' \
      % (keepIt, omitIt, hasMetadata,)

  if keepIt and (not omitIt) and hasMetadata:
    processDir( bugLev, absTopDir, relPath,
      metadataForce, requireIcsd, miscMap,
      relDirs, dirMaps, icsdMaps, relFiles)

  # Recurse to subdirs
  if not omitIt:
    subNames = os.listdir( inDir)
    subNames.sort()
    for subName in subNames:
      subPath = os.path.join( relPath, subName)
      if os.path.isdir( os.path.join( absTopDir, subPath)):
        searchDirs(
          bugLev,
          keepPatterns,
          omitPatterns,
          absTopDir,
          subPath,                    # relPath: relative path so far
          metadataForce,              # metadata to force on all dirs
          requireIcsd,                # require icsd info in absTopDir string
          miscMap,                    # appends to map
          relDirs,                    # parallel: appends to list
          dirMaps,                    # parallel: appends to list
          icsdMaps,                   # parallel: appends to list
          relFiles)                   # appends to list

  else:
    print 'wrapUpload: %-18s %s' % ('skip subTree', inDir,)


#====================================================================


def iterateDirs(
  bugLev,
  keepAbsPaths,
  absTopDir,
  metadataForce,              # metadata to force on all dirs
  requireIcsd,                # require icsd info in absTopDir string
  miscMap,                    # appends to map
  relDirs,                    # parallel: appends to list
  dirMaps,                    # parallel: appends to list
  icsdMaps,                   # parallel: appends to list
  relFiles):                  # appends to list
  '''
  For each path in keepAbsPaths, checks dir contents,
  and appends names to lists of dirs and files.

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.

  * keepAbsPaths (str[]):
    List of absolute paths of dirs to archive.

  * absTopDir (str): Absolute path of the original top of dir tree to upload.
        
  * metadataForce (map):
    Metadata map to be forced on all.
    If specified, the metadata files found
    in the archived dirs are ignored.
    Default: None, meaning each archived
    dir must contain a metadata file.

  * requireIcsd (boolean): if True, the absTopDir string must
    contain ICSD info that :func:`getIcsdMap` can extract.

  * miscMap (map): we call :func:`processDir`, which may increment
    miscMap['numWarn'].

  * relDirs (str[]): we append dir names to this list.

  * dirMaps (map[]): we append maps to this list.
    Parallel with relDirs.

  * icsdMaps (map[]): we append maps (from :func:`getIcsdMap`)
    to this list.
    Parallel with relDirs.

  * relFiles (str[]): We append file names to be archived.

  **Returns**

  * None
  '''

  for inDir in keepAbsPaths:
    if bugLev >= 5:
      print 'iterateDirs: inDir: %s' % (inDir,)
    if not inDir.startswith( absTopDir):
      throwerr('inDir does not start with absTopDir')
    relPath = inDir[len(absTopDir) : ]
    while relPath.startswith('/'):
      relPath = relPath[1:]
    if bugLev >= 5:
      print 'iterateDirs: relPath: %s' % (relPath,)

    processDir( bugLev, absTopDir, relPath,
      metadataForce, requireIcsd, miscMap,
      relDirs, dirMaps, icsdMaps, relFiles)



#====================================================================


def processDir(
  bugLev,
  absTopDir,
  relPath,                    # relative path so far
  metadataForce,              # metadata to force on all dirs
  requireIcsd,                # require icsd info in absTopDir string
  miscMap,                    # appends to map
  relDirs,                    # parallel: appends to list
  dirMaps,                    # parallel: appends to list
  icsdMaps,                   # parallel: appends to list
  relFiles):                  # appends to list
  '''
  Prepares to archive a single directory,
  and appends names to lists of dirs and files.

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.

  * absTopDir (str): Absolute path of the original top of dir tree to upload.

  * relPath (str): Relative path so far, somewhere below absTopDir.
        
  * metadataForce (map):
    Metadata map to be forced on all.
    If specified, the metadata files found
    in the archived dirs are ignored.
    Default: None, meaning each archived
    dir must contain a metadata file.

  * requireIcsd (boolean): if True, the absTopDir string must
    contain ICSD info that :func:`getIcsdMap` can extract.

  * miscMap (map): we may increment miscMap['numWarn'].

  * relDirs (str[]): we append relPath to this list.

  * dirMaps (map[]): we append a map to this list.
    Parallel with relDirs.

  * icsdMaps (map[]): we append a map from :func:`getIcsdMap`)
    to this list.
    Parallel with relDirs.

  * relFiles (str[]): We append file names to be archived.

  **Returns**

  * None
  '''


  inDir = os.path.abspath( os.path.join( absTopDir, relPath))
  if bugLev >= 5:
    print 'processDir: relPath: %s' % (relPath,)
    print 'processDir: inDir: %s' % (inDir,)
  if not os.path.isdir( inDir): throwerr('not a dir')
  subNames = os.listdir( inDir)
  subNames.sort()

  # If metadataForce, we ignore local metadata files.
  reqNames = list( requireNames)    # shallow copy
  optNames = list( optionNames)     # shallow copy
  if metadataForce != None:
    reqNames.remove( metadataName)
    # Skip: the local metadata file is ignored and
    # therefore is misleading:
    # optNames.add( metadataName)

  # Check for reqNames and inc counts in miscMap
  numRequire = len( reqNames)
  numMatch = 0                 # num matches found in reqNames
  foundFlags = []              # parallel with reqNames
  for nm in reqNames:
    subPath = os.path.join( inDir, nm)
    if os.path.isfile( subPath):
      checkFileFull( subPath)
      numMatch += 1
      found = True
    else: found = False
    foundFlags.append( found)

  if numMatch == 0:
    if bugLev >= 1:
      print 'wrapUpload: %-18s %s' % ('    skip dir', inDir,)

  elif numMatch < len( reqNames):
    print ''
    print 'wrapUpload: Warning: incomplete dir: %s' % (inDir,)
    for ii in range(len(reqNames)):
      if foundFlags[ii]: print '  found:   %s' % (reqNames[ii],)
      else:              print '  MISSING: %s' % (reqNames[ii],)
    print ''
    miscMap['numWarn'] += 1

  elif numMatch == len(reqNames):

    # Append file paths to relFiles.
    for nm in reqNames:
      subRelPath = os.path.join( relPath, nm)
      relFiles.append( subRelPath)

    # Check for optNames
    for nm in subNames:
      subRelPath = os.path.join( relPath, nm)
      subFile = os.path.join( inDir, subRelPath)
      if nm in optNames and os.path.isfile( subFile):
        checkFile( subFile)
        relFiles.append( subRelPath)

    # Get stats on all files in inDir
    statMap = {}
    fileNames = os.listdir( inDir)
    fileNames.sort()
    for nm in fileNames:
      smap = getStatMap( bugLev, os.path.join( inDir, nm))
      statMap[nm] = smap

    # Append to 3 parallel arrays: relDirs, dirMaps, icsdMaps
    relDirs.append( relPath)
    dirMaps.append( {
      'absPath': inDir,
      'relPath': relPath,
      'statMap': statMap,
    })
    try:
      icsdMap = getIcsdMap( bugLev, absTopDir, relPath)
    except Exception, exc:
      print 'processDir: no icsd info found for absTopDir: %s' \
        % (absTopDir,)
      if requireIcsd: throwerr(
        'icsd info not found.  absTopDir: %s  traceback:\n%s' \
        % (absTopDir, traceback.format_exc( limit=None),))
      icsdMap = {}
    icsdMaps.append( icsdMap)

  else: throwerr('invalid numMatch')


#====================================================================

# Calls os.stat on fpath and returns map: statInfoName -> value

def getStatMap( bugLev, fpath):
  '''
  Returns a map of fileName -> os.stat() value for a given directory.

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.

  * fpath (str): Path of the directory to list.

  **Returns**

  * A map of fileName -> os.stat() value for the fpath directory.
  '''

  absName = os.path.abspath( fpath)
  statInfo = os.stat( absName)
  if bugLev >= 10:
    print 'getStatMap: fpath: %s  absName: %s statInfo: %s' \
      % ( fpath, absName, statInfo,)
  smap = {}
  for key in dir( statInfo):
    if key.startswith('st_'):
      value = getattr( statInfo, key, None)
      smap[key] = value
  return smap


#====================================================================

# Recursively get "stat" info (filename, len, dates)
# for a directory tree.  Uses absolute paths.
# Appends to statInfos, which is a list of pairs: [absName, statinfoMap].

def getStatInfos( bugLev, fname, statInfos):
  '''
  Recursive: creates a list of statInfoMaps for an entire tree.
  
  Appends a map of fileName -> os.stat()
  to the statInfos list, and recurses on subdirs.

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.

  * fname (str): The current directory to list.

  * fname (map[]): We append to this list of maps.

  **Returns**

  * None
  '''

  absName = os.path.abspath( fname)

  smap = getStatMap( bugLev, absName)
  statInfos.append( (absName, smap,) )

  if os.path.isdir( absName):
    subNames = os.listdir( absName)
    subNames.sort()
    for nm in subNames:
      subPath = os.path.join( fname, nm)
      getStatInfos( bugLev, subPath, statInfos)         # recursion



#====================================================================

# Creates a map of ICSD info based on the dir name

def getIcsdMap( bugLev, absTopDir, relPath):
  '''
  Creates a map of ICSD info based on the dir name.

  Example parsing inDir: ::

    .../icsd_083665/icsd_083665.cif/ls-anti-ferro-7/relax_cellshape/1
             ^^^^^^                 ^^^^^^^^      ^ ^^^^^^^^^^^^^^^ ^
            icsdNum                 magType  magNum relaxType       relaxNum

  Resulting map: ::

    icsdMap = {
      'icsdNum'   : 83665,
      'magType'   : 'lsaf',
      'magNum'    : 7,
      'relaxType' : 'rc',
      'relaxNum'  : 1,
    }

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.

  * absTopDir (str): Absolute path of the original top of dir tree to upload.

  * relPath (str): Relative path, somewhere below absTopDir.

  **Returns**

  * map similar to the above.
  '''

  inDir = os.path.abspath( os.path.join( absTopDir, relPath))
  absPath = os.path.abspath( inDir)

  # Extract the ICSD number from the path '.../icsd_dddddd/...'
  mat = re.match('^.*/icsd_(\d{6})/.*$', absPath)
  if mat == None:
    throwerr('no icsd id found in inDir name: "%s"' % (absPath,))
  icsdNum = int( mat.group(1))

  # Extract magnetic moment type from absPath
  magType = None
  magNum = 0
  pairs = [['/hs-ferro',      'hsf'],
           ['/hs-anti-ferro', 'hsaf'],
           ['/ls-ferro',      'lsf'],
           ['/ls-anti-ferro', 'lsaf'],
           ['/non-magnetic',  'nm']]
  for (tname,tcode) in pairs:
    ix = absPath.find( tname)
    if ix >= 0:
      magType = tcode
      if tcode in ['hsaf', 'lsaf']:
        rest = absPath[(ix+len(tname)):]
        mat = re.match('^-(\d+).*$', rest)
        if mat == None:
          throwerr('no magNum found in absPath: "%s"' % (absPath,))
        magNum = int( mat.group(1))
      break
  if magType == None:
    throwerr('no magType found in absPath: "%s"' % (absPath,))

  # Extract relaxType from absPath

  # If absPath contains 'relax_cellshape', set relaxType = 'rc'
  # and relaxNum = the number of the subfolder.  Similarly for 'relax_ions'.
  relaxType = 'std'
  relaxNum = 0
  pairs = [['relax_cellshape', 'rc'],
           ['relax_ions',      'ri']]
  for (tname,tcode) in pairs:
    ix = absPath.find( tname)
    if ix >= 0:
      relaxType = tcode
      rest = absPath[(ix+len(tname)):]
      mat = re.match('^/(\d+).*$', rest)
      if mat == None:
        throwerr('no subfolder found in absPath: "%s"' % (absPath,))
      relaxNum = int( mat.group(1))
      break

  # Save the info from the path name and statInfo
  icsdMap = {
    'icsdNum'   : icsdNum,
    'magType'   : magType,
    'magNum'    : magNum,
    'relaxType' : relaxType,
    'relaxNum'  : relaxNum,
  }

  return icsdMap



#====================================================================



def unused_extractPotcar( fname):
  '''
  (No longer used): Reads and saves the header sections from a POTCAR file.
  
  Saves every section starting with 'PAW_PBE' to the following
  line 'Description'.

  **Parameters**:

  * fname (str): Name of the input POTCAR file.

  **Returns**

  * List of pairs: [ specieName, listOfSavedLines]
  '''

  pseudos = []          # list of pairs: [ specieName, listOfSavedLines]
  with open( fname) as fin:
    state = False                   # not capturing
    specie = None
    saves = []
    iline = 0
    while True:
      line = fin.readline()
      if line == '': break
      iline += 1

      mat = re.match(r'^\s*PAW_PBE\s+(\S+)\s+.*$', line)
      if mat:
        state = True                # capturing
        specie = mat.group(1)

      mat = re.match(r'^\s*Description\s*$', line)
      if mat:
        pseudos.append( [ specie, saves])
        state = False               # not capturing
        specie = None
        saves = []

      if state:                     # if capturing
        saves.append( line)

  return pseudos


#====================================================================


def parseMetadata( fpath):
  '''
  Parses a metadata file and returns a corresponding map.
  
  **Parameters**:

  * fpath (str): Name of the input metadata file.

  **Returns**

  * Map of metadata values.  The map structure is:

    =============  ==========  ===========================================
    Key            Value Type  Source description
    =============  ==========  ===========================================
    firstName      str         Researcher first name
    lastName       str         Researcher last name
    parents        str[]       comma separated list of sha512sum(s) of the
                               vasprun.xml files of previous runs, if any
    publications   str[]       comma separated list of DOIs
                               without the leading ``http://``
    standards      str[]       comma separated list of standardized
                               keywords
    keywords       str[]       comma separated list of any keywords
    notes          str         textual notes
    =============  ==========  ===========================================
  '''

  parentsTag = 'parents'
  firstNameTag = 'firstName'
  lastNameTag = 'lastName'
  publicationsTag = 'publications'
  standardsTag = 'standards'
  keywordsTag = 'keywords'
  notesTag = 'notes'

  requiredFields = [firstNameTag, lastNameTag,
    publicationsTag, standardsTag, keywordsTag, notesTag]

  checkFileFull( fpath)
  with open( fpath) as fin:
    lines = fin.readlines()       # not stripped.  Includes final \n.

  metaMap = {}
  if len(lines) < 2:
    throwerr('invalid metadata.  file: \"%s\"' % ( fpath,))

  iline = 0
  while iline < len(lines):
    line = lines[iline]
    if re.match(r'^\s*$', line) or line.startswith('#'):
      iline += 1           # ignore blank lines and comments
    else:
      mat = re.match(r'^:(\w+):(.*)$', line)
      if not mat:
        throwerr('invalid metadata.  approx iline: %d  file: \"%s\"' \
          % (iline, fpath,))
      field = mat.group(1)
      value = mat.group(2)        # init value

      if metaMap.has_key(field):
        throwerr('multiple spec of field: "%s"  file: "%s"\n' \
          % (field, fpath,))

      if field in [parentsTag, publicationsTag, standardsTag, keywordsTag]:
        # Strip before we test for trailing comma below
        value = value.strip()

      # Append lines onto value as we scan for
      # the next comment or field
      iline += 1
      while iline < len(lines):
        line = lines[iline]
        if line.startswith('#') or re.match(r'^:(\w+):(.*)', line): break
        if field in [parentsTag, publicationsTag, standardsTag, keywordsTag]:
          # If user forgot a trailing comma, help them out.
          if len(value.strip()) > 0 and not value.endswith(','):
            value += ','
          value += line.strip()
        else:
          value += line        # line includes \n
        iline += 1

      value = value.strip()     # get rid of whitespace at ends

      if field in [firstNameTag, lastNameTag]:
        if re.search(r'[^-a-zA-Z]', value) \
          or (not re.match('^[A-Z]$', value[0])) \
          or (not re.match('^[a-zA-Z]$', value[-1])):
          throwerr('invalid name: "%s"  file: "%s"\n' % (value, fpath,))
        metaMap[field] = value

      elif field in [parentsTag, publicationsTag, standardsTag, keywordsTag]:
        # Convert value to list of keywords.
        # Insure keywords don't contain illegal chars.
        vals = []
        toks = value.split(',')
        for tok in toks:
          tok = tok.strip()
          errMsg = ''
          if field == parentsTag:
            if len(tok) != 128 or re.search(r'[^a-f0-9]', tok):
              errMsg += 'Invalid parent (must be 128 chars).\n'
          if field == publicationsTag:
            if field.startswith('http'):
              errMsg += 'Specify DOI without the initial http://\n'
          if field in [standardsTag, keywordsTag]:
            if len(tok) < 1  \
              or re.search(r'[^-a-zA-Z0-9]', tok) \
              or (not re.match('^[a-zA-Z]$', tok[0])) \
              or (not re.match('^[a-zA-Z0-9]$', tok[-1])):
              errMsg += 'Invalid keyword.\n'
          if len(errMsg) > 0:
            errMsg += '  Invalid item: "%s"\n' % (tok,) \
              + '  Containing value: "%s"\n' % (value,) \
              + '  file: %s\n' % (fpath,)
            throwerr( errMsg)
          vals.append( tok)
        metaMap[field] = vals         # set list

      elif field == notesTag:
        metaMap[field] = value       # set text

      else:
        throwerr('unknown field: \"%s\"  approx iline: %d  file: \"%s\"' \
          % (field, iline, fpath,))

  for nm in requiredFields:
    if not metaMap.has_key(nm): 
      throwerr('missing field: \"%s\" in file: \"%s\"' % (nm, fpath,))

  legalStandards = [
    'fere',
    'gwvd',
    'wave',
    'aexp',
    'post-lopt',
    'post-chi',
    'post-dos',
  ]
  for key in metaMap[ standardsTag]:
    if key not in legalStandards:
      throwerr('illegal standard "%s" in file: ' (key, fpath,))

  return metaMap


#====================================================================


def checkFileFull( fname):
  '''
  Insures that fname exists and has length > 0.
  
  **Parameters**:

  * fname (str): Name of the input file.

  **Returns**

  * None

  **Raises**:

  * Exception if fname does not exist or has length == 0.
  '''

  checkFile( fname)
  if os.path.getsize( fname) == 0:
    throwerr('file is empty: \"%s\"' % (fname,))

#====================================================================

def checkFile( fname):
  '''
  Insures that fname exists.  It may have length == 0.
  
  **Parameters**:

  * fname (str): Name of the input file.

  **Returns**

  * None

  **Raises**:

  * Exception if fname does not exist.
  '''

  if (type(fname).__name__ not in ('str', 'unicode')) or len(fname) == 0:
    throwerr('invalid file name: "%s"' % (fname,))
  if not os.path.isfile( fname):
    throwerr('file not found: \"%s\"' % (fname,))
  if not os.access( fname, os.R_OK):
    throwerr('file is not readable: \"%s\"' % (fname,))

#====================================================================

def runSubprocess( bugLev, wkDir, args, showStdout):
  '''
  Calls the executable indicated by args and waits for completion.
  
  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.

  * wkDir (str): The working directory to use for the subprocess.

  * args (str[]): The executable name (in args[0]) followed by
    the command line arguments in args[1:].

  * showStdout (boolean): If True, print the stdout from the subprocess.

  **Returns**

  * None

  **Raises**:

  * Exception if subprocess rc != 0.
  '''

  if bugLev >= 1:
    print 'runSubprocess: args: %s' % (args,)
    print 'runSubprocess: cmd: %s' % (' '.join(args),)
  proc = subprocess.Popen(
    args,
    shell=False,
    cwd=wkDir,
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    bufsize=10*1000*1000)
  (stdout, stderr) = proc.communicate()
  rc = proc.returncode
  if rc != 0:
    msg = 'subprocess failed.\n'
    msg += 'wkDir: %s\n' % (wkDir,)
    msg += 'args: %s\n' % (args,)
    msg += 'rc: %d\n' % (rc,)
    msg += '\n===== stdout:\n%s\n' % (stdout,)
    msg += '\n===== stderr:\n%s\n' % (stderr,)
    throwerr( msg)
  if showStdout:
    print 'runSubProcess: len(stderr): %d' % (len(stderr),)
    print 'runSubProcess: len(stdout): %d' % (len(stdout),)
    if len(stderr) > 0:
      print '\n===== stderr:\n%s\n' % (stderr,)
    if len(stdout) > 0:
      print '\n===== stdout:\n%s\n' % (stdout,)

#====================================================================



def findNumFiles( tag, dir):
  '''
  Finds the number of files having name == tag in the tree at dir.
  Yes, Python has os.walk, but this is better.

  **Parameters**:

  * tag (str): The name to search for.

  * dir (str): The root of the directory tree to search.

  **Returns**

  * integer number of matches.
  '''

  if not os.path.isdir( dir): throwerr('not a dir: %s' % (dir,))
  nms = os.listdir( dir)
  nms.sort()
  count = 0
  for nm in nms:
    if nm == tag: count += 1
    subDir = dir + '/' + nm
    if os.path.isdir( subDir):
      count += findNumFiles( tag, subDir)      # recursion
  return count

#====================================================================

# Coord with parseUui, below.
def formatUui( curDate, userId, absTopDir):
  '''
  Formats a uui (wrapId).

  A wrapId looks like: ::

    @2013.08.13@12.58.22.735311@someUser@home.someUser.redmesa.old.td.testlada.2013.04.06.Fe.O@

  **Parameters**:

  * curDate (datetime.datetime): The current date.

  * userId (str): The current user id.

  * absTopDir (str): The absolute path of the top dir.

  **Returns**

  * A wrapId
  '''

  if not absTopDir.startswith('/'): throwerr('absTopDir not abs')
  modDir = absTopDir[1:]    # get rid of initial /
  modDir = modDir.replace('/', '.')     # get rid of /
  modDir = modDir.replace('@', '.')     # get rid of @
  uui = '@%s@%s@%s@' \
    % (curDate.strftime('%Y.%m.%d@%H.%M.%S.%f'), userId, modDir,)
  return uui

#==========

# Coord with formatUui, above.
# If matches, returns wrapId == stg.
# Else returns None.

def parseUui( stg):
  '''
  Parses a uui (wrapId).

  A wrapId looks like: ::
    @2013.08.13@12.58.22.735311@someUser@home.someUser.redmesa.old.td.testlada.2013.04.06.Fe.O@

  The input string may have subdirs info after the initial wrapId.

  **Parameters**:

  * stg (str): The string to be parsed.


  **Returns**

  * If stg is a valid wrapId, returns the wrapId == stg.
    Else returns None.
  '''

  uuiPattern = r'^(@(\d{4}\.\d{2}\.\d{2})@(\d{2}\.\d{2}\.\d{2}\.\d{6})@([^./@]*)@([^/@]*)@)'
  res = None
  mat = re.match( uuiPattern, stg)
  if mat:
    wrapId = mat.group(1)
    dateStg = mat.group(2)
    timeStg = mat.group(3)
    userid = mat.group(4)
    dir = mat.group(5)
    adate = datetime.datetime.strptime(
      dateStg + ' ' + timeStg, '%Y.%m.%d %H.%M.%S.%f')
    res = wrapId     # Could return (wrapId, adate, userid, dir)
  return res

#====================================================================

def printMap( tag, vmap, maxLen):
  '''
  Prints a map.

  **Parameters**:

  * tag (str): Explanatory name of the map.

  * vmap (map): The map to print.

  * maxLen (int): The max length to use in printing a value.

  **Returns**

  * None
  '''

  print '\n%s' % (tag,)
  if vmap == None:
    print '    Map is None.'
  else:
    print '    Map len: %d' % (len(vmap),)
    keys = vmap.keys()
    keys.sort()
    for key in keys:
      val = str( vmap[key])
      if len(val) > maxLen: val = val[:maxLen] + '...'
      print '    %s: %s' % (key, val,)

#====================================================================

def formatMatrix( mat):
  '''
  Formats a 2D matrix.

  **Parameters**:

  * mat (float[][] or numpy 2D array): input matrix

  **Returns**

  * string representation of the matrix.
  '''

  msg = ''
  for ii in range(len(mat)):
    row = mat[ii]
    msg += '  [%2d]  ' % (ii,)
    for jj in range(len(row)):
      msg += '  %8.4f' % (mat[ii][jj],)
    msg += '\n'
  return msg


#====================================================================

def parseBoolean( stg):
  if stg.lower() in ['false', 'no']: res = False
  elif stg.lower() in ['true', 'yes']: res = True
  else: throwerr('invalid boolean: "%s"' % (stg,))
  return res

#====================================================================


# Print a logging message.

def logit(msg):
  '''
  Prints a time-stamped message for logging.

  Yes, Python has a logging package.
  This is better since it handles milliseconds
  and is far easier to use.

  **Parameters**:

  * msg (msg): The message to print.

  **Returns**

  * None
  '''

  tm = time.time()
  itm = int( math.floor( tm))
  delta = tm - itm
  loctm = time.localtime( itm)

  stg = time.strftime( '%Y-%m-%d %H:%M:%S', loctm)
  mdelta = int( math.floor( 1000 * delta))
  stg += '.%03d' % (mdelta,)

  print '%s %s' % (stg, msg,)

#====================================================================

def throwerr( msg):
  '''
  Prints an error message and raises Exception.

  **Parameters**:

  * msg (str): Error message.

  **Returns**

  * (Never returns)
  
  **Raises**

  * Exception
  '''

  raise Exception( msg)


#====================================================================

if __name__ == '__main__': main()
