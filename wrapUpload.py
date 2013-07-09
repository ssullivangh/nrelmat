#!/bin/env python

import datetime, json, math, os, pwd, re
import shutil, socket, stat, subprocess, sys, time


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
  'pickle',
  'stderr',
  'stdout'
]


digestDirName = 'wrapUpload.archive'

overviewJsonName = 'overview.json'
wrapUploadJsonName = 'wrapUpload.json'

#====================================================================

def badparms( msg):
  print '\nError: %s' % (msg,)
  print 'Parms:'
  print '  -bugLev     <int>      debug level.  Default: 0'
  print '  -overview   <string>   overview or description.'
  sys.exit(1)


#====================================================================


def main():

  bugLev = 0
  overview = None

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if   key == '-bugLev': bugLev = int( val)
    elif key == '-overview': overview = val
    else: badparms('unknown key: "%s"' % (key,))

  if overview == None: badparms('parm not specified: -overview')

  curDir = '.'

  digestDir = os.path.join( curDir, digestDirName)
  if os.path.lexists( digestDir):
    shutil.rmtree( digestDir)

  statInfos = []
  getStatInfos( bugLev, curDir, statInfos)

  # Get the relative paths of all files to be archived, starting at curDir.
  archPaths = []
  miscMap = {
    'numError': 0,
    'numOkMetadata': 0
  }
  checkArchPath( bugLev, curDir, miscMap, archPaths)

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
      del envMap[key]

  curDate = datetime.datetime.now()
  userId = pwd.getpwuid(os.getuid())[0]
  hostName = socket.gethostname()

  # Get some statistics
  numIncar = findNumFiles('INCAR', curDir)
  numVasprun = findNumFiles('vasprun.xml', curDir)
  numOutcar = findNumFiles('OUTCAR', curDir)
  numMetadata = findNumFiles('metadata', curDir)

  if miscMap['numError'] > 0:
    throwerr('Found %d errors.  S notes above' % (numError,))
  if numMetadata != miscMap['numOkMetadata']:
    throwerr('num metadata: %d  num ok: %d' \
      % (numMetadata, miscMap['numOkMetadata'],))

  msg = 'wrapUpload: file summary:\n'
  msg += '  num INCAR files found:         %4d    Num kept: %4d\n' \
    % (numIncar, numMetadata)
  msg += '  num OUTCAR files found:        %4d    Num kept: %4d\n' \
    % (numOutcar, numMetadata)
  msg += '  num vasprun.xml files found:   %4d    Num kept: %4d\n' \
    % (numVasprun, numMetadata)
  msg += '  num metadata files found:      %4d    Num kept: %4d\n' \
    % (numMetadata, numMetadata)
  logit( msg)


  # Coord with fillDbVasp.py fillTable
  overMap = {
    'curDate': curDate.strftime('%Y-%m-%dT%H:%M:%S.%f'),
    'userId': userId,
    'hostName': hostName,
    'numIncar': numIncar,
    'numOutcar': numOutcar,
    'numVasprun': numVasprun,
    'uploadDir': os.path.abspath( curDir),
    'overview': overview,
    'envMap': envMap,
    'statInfos': statInfos,
    'archPaths': archPaths}
  jFile = os.path.join( digestDir, overviewJsonName)
  with open( jFile, 'w') as fout:
    json.dump( overMap, fout, sort_keys=True, indent=2,
      separators=(',', ': '))

  listFile = os.path.join( digestDir, 'digest.list')
  archPaths.append( jFile)
  archPaths.append( listFile)
  with open( listFile, 'w') as fout:
    for path in archPaths:
      print >> fout, path

  logit('wrapUpload: beginning tar (this could take several minutes)')
  uui = curDate.strftime('arch.%Y.%m.%d.tm.%H.%M.%S.%f')
  uui += '.user.%s.host.%s.digest' % (userId, hostName,)
  fBase = os.path.join( digestDir, uui)
  tarFile = fBase + '.tgz' 
  flagFile = fBase + '.flag' 
  idFile = fBase + '.id' 

  args = ['/bin/tar', '-czf', tarFile, '-T', listFile, '--mode=660']
  runSubprocess( bugLev, os.getcwd(), args)

  with open( flagFile, 'w') as fout:
    pass   # just create the file

  with open( idFile, 'w') as fout:
    fout.write( rsa_id)
  os.chmod( idFile, stat.S_IRUSR + stat.S_IWUSR)    # r, w for user only

  args = ['chmod', '660', tarFile, flagFile]
  runSubprocess( bugLev, os.getcwd(), args)

  logit('wrapUpload: beginning scp (this could take several minutes)')
  args = ['/usr/bin/scp', '-B', '-p', '-i', idFile,
    '-o', 'StrictHostKeyChecking=no',
    tarFile, flagFile,
    'scpuser@cid-dev.hpc.nrel.gov:/data/incoming']
  runSubprocess( bugLev, os.getcwd(), args)

  # xxx os.remove( idFile)




#====================================================================


def getStatMap( bugLev, fname):
  absName = os.path.abspath( fname)
  statInfo = os.stat( absName)
  if bugLev >= 5:
    print 'getStatMap: fname: %s  absName: %s statInfo: %s' \
      % ( fname, absName, statInfo,)
  smap = {}
  for key in dir( statInfo):
    if key.startswith('st_'):
      value = getattr( statInfo, key, None)
      smap[key] = value
  return smap


#====================================================================

# Recursively get "stat" info (filename, len, dates)
# for a directory tree.

def getStatInfos( bugLev, fname, statInfos):
  absName = os.path.normpath( fname)
  statInfo = os.stat( absName)
  if bugLev >= 5:
    print 'getStatInfos: fname: %s  absName: %s statInfo: %s' \
      % ( fname, absName, statInfo,)
  smap = {}
  for key in dir( statInfo):
    if key.startswith('st_'):
      value = getattr( statInfo, key, None)
      smap[key] = value
  statInfos.append( (absName, smap,) )
  if os.path.isdir( absName):
    subNames = os.listdir( absName)
    subNames.sort()
    for nm in subNames:
      subPath = os.path.join( fname, nm)
      getStatInfos( bugLev, subPath, statInfos)         # recursion



#====================================================================


# Recursively get the relative paths of all files to be archived,
# starting at dirName.

def checkArchPath( bugLev, inDir, miscMap, archPaths):
  inDir = os.path.normpath( inDir)
  if bugLev >= 5:
    print 'checkArchPath: inDir: %s' % ( inDir,)
  if not os.path.isdir( inDir): throwerr('not a dir')
  subNames = os.listdir( inDir)
  subNames.sort()

  if not metadataName in subNames:
    print 'wrapUpload: no metadata file; skipping dir: %s' % (inDir,)
  else:
    getArchPath( bugLev, inDir, miscMap, archPaths)

  # Recurse to subdirs
  for subName in subNames:
    subPath = os.path.join( inDir, subName)
    if os.path.isdir( subPath):
      checkArchPath( bugLev, subPath, miscMap, archPaths)


#====================================================================


def getArchPath( bugLev, inDir, miscMap, archPaths):
  if not os.path.isdir( inDir): throwerr('not a dir')

  inDir = os.path.normpath( inDir)
  subNames = os.listdir( inDir)
  subNames.sort()

  # Check for requireNames
  numMatch = 0                 # num matches found in requireNames
  foundFlags = []
  for nm in subNames:
    subPath = os.path.join( inDir, nm)
    if nm in requireNames and os.path.isfile( subPath):
      numMatch += 1
      foundFlags.append( True)
    else: foundFlags.append( False)

  if numMatch == len(requireNames):
    # Make sure we can read the file, and append it to archPaths.
    for nm in requireNames:
      subPath = os.path.join( inDir, nm)
      checkFileFull( subPath)
      archPaths.append( subPath)

    writeDirDigest( bugLev, inDir)
    archPaths.append( os.path.join( inDir, wrapUploadJsonName))
    miscMap['numOkMetadata'] += 1

  else:
    print 'wrapUpload: Error: incomplete dir: %s' % (inDir,)
    for ii in range(len(requireNames)):
      if foundFlags[ii]: print '  found:   %s' % (requireNames[ii],)
      else:              print '  MISSING: %s' % (requireNames[ii],)
    miscMap['numError'] += 1

  # Check for optionNames
  for nm in subNames:
    subPath = os.path.join( inDir, nm)
    if nm in optionNames and os.path.isfile( subPath):
      checkFile( subPath)
      archPaths.append( subPath)



#====================================================================

# Create wrapUpload.json

def writeDirDigest( bugLev, inDir):
  absPath = os.path.abspath( inDir)

  # Extract the ICSD number from the path '.../icsd_dddddd/...'
  mat = re.match('^.*/icsd_(\d{6})/.*$', absPath)
  if mat == None:
    throwerr('no icsd id found in inDir name: "%s"' % (absPath,))
  icsdNum = int( mat.group(1))

  # Extract magnetic moment type from absPath
  magType = None
  magNum = 0
  pairs = [['hs-ferro',      'hsf'],
           ['hs-anti-ferro', 'hsaf'],
           ['ls-ferro',      'lsf'],
           ['ls-anti-ferro', 'lsaf'],
           ['non-magnetic',  'nm']]
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

  # Get stats on all files in absPath
  statMap = {}
  fileNames = os.listdir( absPath)
  fileNames.sort()
  for nm in fileNames:
    smap = getStatMap( bugLev, os.path.join( absPath, nm))
    statMap[nm] = smap

  # Get the user-specified metadata file
  metaPath = os.path.join( absPath, metadataName)
  metaMap = parseMetadata( metaPath)      # make sure format is valid

  # Extract info from inDir
  smallMap = {
    'icsdNum'   : icsdNum,
    'magType'   : magType,
    'magNum'    : magNum,
    'relaxType' : relaxType,
    'relaxNum'  : relaxNum,
    'absPath'   : absPath,
    'statMap'   : statMap,
  }
  # Copy metaMap into smallMap
  for key in metaMap.keys():
    smallMap['meta_' + key] = metaMap[key]

  # Write smallMap to wrapUpload.data
  jFile = os.path.join( inDir, wrapUploadJsonName)
  if os.path.lexists( jFile):
    os.remove( jFile)
  with open( jFile, 'w') as fout:
    json.dump( smallMap, fout, sort_keys=True, indent=2,
      separators=(',', ': '))





#====================================================================



def unused_extractPotcar( fname):
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

  # Required metadata fields comprised of comma separated words
  commaNames = ['standards', 'keywords']

  # Required metadata text fields
  textNames = [ 'firstName', 'lastName', 'publication', 'notes']

  checkFileFull( fpath)
  with open( fpath) as fin:
    lines = fin.readlines()

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
      value = mat.group(2)

      # Scan for the end of the value -- until the next comment or field
      iline += 1
      while iline < len(lines):
        line = lines[iline]
        if line.startswith('#') or re.match(r'^:(\w+):(.*)', line): break
        value += '\n' + line
        iline += 1
      value = value.strip()  # clean up whitespace at ends, not within value

      if field in commaNames:
        # Convert value to list of keywords.
        # Insure keywords don't contain whitespace.
        toks = value.split(',')
        value = []
        for tok in toks:
          tok = tok.strip()
          if re.search(r'\s', tok):
            throwerr('bad keyword: \"%s\"  approx iline: %d  file: \"%s\"' \
              % (tok, iline, fpath,))
          value.append( tok)

      elif field in textNames:
        pass

      else:
        throwerr('unknown field: \"%s\"  approx iline: %d  file: \"%s\"' \
          % (field, iline, fpath,))

      metaMap[field] = value

  for nm in commaNames + textNames:
    if not metaMap.has_key(nm): 
      throwerr('missing field: \"%s\" in file: \"%s\"' % (nm, file,))

  return metaMap


#====================================================================


rsa_id = '''-----BEGIN RSA PRIVATE KEY-----
MIIEoQIBAAKCAQEAxm4ocbBMCbsF1YTCRXrLy/oUjrdi6aHD8L4/3k1CfFs6SkzS
7qFYmsDgov5Ukv3kJcd8W8sqgyb5K1bOcgMukJYEGyo6JgL/Aeupzv0Wv/FWfJvT
r1MnLVfVsvewdWgNLO9xiLU2zzIZr8bA+SMQKpe1kbKHv+CDsePGs6QYQ2dRQEuO
dFPKy4l4oW9XREvRVTiAikp6mBn1nd9K7Q/k82hEIq/Jq1ON9MHHgQiXvDVc8ivE
ce0JRdW9vyH7hEHYjv363vt9FRw0/hSl5QTyKQXRVP+1WfmyOkIZggAXC7ODElao
KI9i9o2YMhDy08cNfKR6Z3bb965O38Vh2hoLhwIBIwKCAQEAr8CneqN2jEaQI4Q3
ClbRw0s2x4x8LgROdiTZe8DF29vF6gmHoCiBraOFIqa/7+gweTuoqRMIZYjrUkWS
R7ms5nY+JrBfY37/HvVNQk3g8yY2qOHKHvHg3wSnVV8KAZaslYOfEq8h6rdYlF+U
+evbHmkdKUZa+mfFGecAczmR1UtSTfAsDx9SCbIivqDkmfICsAFn7idY0fi+ei7O
6bVulfocqYiYNz+X5eQfZBtCo4Finl9YPDxIY6GfT/xkt11HiGHcZ3LmlGpXPHdH
G44w0g0FuYn4IHGiH00EOpZVBMTVOugMm+Ukhb5l9VXwWRK+DCQyPAIXgHFaf5fQ
aEf1OwKBgQDi2WNbF2pQ2v+YGvBPI8z3cPeCtBtxOuMMYBrxP4G6dMmwyFPn/zdf
izze0atHMxJBYJH9lPE8m3RWBIKMjJyBRbiPairt8H4uCfuFhlbBAxxC3MpuM3hD
xtAgt8AWJTB0FF1FnVxoRT1bUPUcGR8cuaVMiVp49+TakGbUtwmlyQKBgQDf7eFL
8P/rxI81KyQ3k7fvoarCTW33qfTH3RvjrfLfMCEYJ1ZOlwXuRO60ujZHXOvdxgTW
2wpRpT+S0+3T9xK8M2uTpS3M4CX3Cqs7cR4rk5jKEhVgjkMzR9j0A/le2N6iYKDQ
LcTqO1g9YMMRsO2eUjEmsyJIdwdo+R6AzlwOzwKBgBNxuA8fQ6CHzMPlDUicqysm
8KTNm/PDOAhgAk8xVEMulPHlSQVBwururXIvOpETAZCTP7amXdH+sjNCNxNcgnF7
ATDdNuEx3u4A2wtx6i3NEQ0LnFKWsol3cOzcjM6yuwKiqOi1t3am2V+ZOZSxsjWp
gzJyLFOC9lvgfde36uJTAoGAUyx4QMc6fCRvtKmfvN8YbvLnp0FUuxM9qVIgTUCc
CcFrYL4nXwTk8hmafaRAC+CvYQBoMovfQuWbRSolItgc5tFFNtbzwSAOGe4FFhQS
hTbSWa7x/0rIgMLqLr+lxCSqdtNu7jzivWZ/3EiC9/FCUL9xV4RdMNvA7HnJgEyl
2Z0CgYAfy53byUeqdGUT17EaXu+e8Fvp5JglIMIHshGvmSHiTB8cK6wMmp/W7BQ4
l6gWE8+SIcGK7jik3L38Mqy41ifhwQ5y1zDAkP0QOiY1i1W9xEWXDtMDBbFFwl83
DfCsjZdxC+DOz13qAEMd4+sDfapc+v0nSGvUvAiyJT6v6XH2jg==
-----END RSA PRIVATE KEY-----
'''

#====================================================================

def checkFileFull( fname):
  checkFile( fname)
  if os.path.getsize( fname) == 0:
    throwerr('file is empty: \"%s\"' % (fname,))

#====================================================================

def checkFile( fname):
  if not os.path.isfile( fname):
    throwerr('file not found: \"%s\"' % (fname,))
  if not os.access( fname, os.R_OK):
    throwerr('file is not readable: \"%s\"' % (fname,))

#====================================================================

def runSubprocess( bugLev, wkDir, args):
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
  rc = proc.wait()
  if rc != 0:
    msg = 'subprocess failed.\n'
    msg += 'wkDir: %s\n' % (wkDir,)
    msg += 'args: %s\n' % (args,)
    msg += 'rc: %d\n' % (rc,)
    msg += '\n===== stdout:\n%s\n' % (stdout,)
    msg += '\n===== stderr:\n%s\n' % (stderr,)
    throwerr( msg)

#====================================================================


# Find the number of files with name==tag in tree at dir.
# Yes, Python has os.walk, but this is better.

def findNumFiles( tag, dir):
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


# Print a logging message.
# Yes, Python has a logging package.
# This is better since it handles milliseconds
# and is far easier to use.

def logit(msg):
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
  raise Exception( msg)


#====================================================================

if __name__ == '__main__': main()
