#!/bin/env python

import datetime, json, math, os, pwd, re
import shutil, socket, stat, subprocess, sys, time


# Name of the metadata file
metadataName = 'metadata'


# Names of required files
requireNames = [
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


# Work and archive subdir of the top level dir.
digestDirName = 'wrapUpload.archive'

# Name of overMap json file within digestDirName
overMapFile = 'overview.json'

# Name of smallMap json file within each archived dir
smallMapFile = 'wrapUpload.json'

#====================================================================

def badparms( msg):
  print '\nError: %s' % (msg,)
  print 'Parms:'
  print '  -bugLev     <int>      debug level.  Default: 0'
  sys.exit(1)


#====================================================================


def main():

  bugLev = 0

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if   key == '-bugLev': bugLev = int( val)
    else: badparms('unknown key: "%s"' % (key,))

  curDir = '.'

  # Get metadata
  metaPath = os.path.join( curDir, metadataName)
  metaMap = parseMetadata( metaPath)

  digestDir = os.path.join( curDir, digestDirName)
  if os.path.lexists( digestDir):
    shutil.rmtree( digestDir)

  statInfos = []
  getStatInfos( bugLev, curDir, statInfos)

  # Init counters in miscMap
  relDirs = []            # list of dirs we archive
  archPaths = []          # list of files to archive
  miscMap = {
    'numWarn': 0,
  }
  for nm in requireNames:
    miscMap['tot_'+nm] = findNumFiles( nm, curDir)
    miscMap['fnd_'+nm] = 0

  # Get the relative paths of all files to be archived, starting at curDir.
  getArchPath( bugLev, metaMap['omit'], curDir, miscMap, relDirs, archPaths)

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

  curDate = datetime.datetime.now()
  userId = pwd.getpwuid(os.getuid())[0]
  hostName = socket.gethostname()

  numWarn = miscMap['numWarn']
  if numWarn > 0:
    ##print '\nFound %d warnings.  See notes above' % (numWarn,)
    throwerr('\nFound %d warnings.  See notes above' % (numWarn,))

  # Print statistics
  msg = 'wrapUpload: file summary:\n'
  for nm in requireNames:
    totNum = miscMap['tot_'+nm]
    fndNum = miscMap['fnd_'+nm]
    msg += '  Total num %-12s files found: %4d    Kept: %4d  Omitted: %4d\n' \
      % (nm, totNum, fndNum, totNum - fndNum,)
  logit( msg)


  # Coord with fillDbVasp.py fillTable
  overMap = {
    'miscMap': miscMap,
    'metaMap': metaMap,
    'curDate': curDate.strftime('%Y-%m-%dT%H:%M:%S.%f'),
    'userId': userId,
    'hostName': hostName,
    'uploadDir': os.path.abspath( curDir),
    'envMap': envMap,
    'statInfos': statInfos,
    'relDirs': relDirs,
    'archPaths': archPaths,
  }
  jFile = os.path.join( digestDir, overMapFile)
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

  os.remove( idFile)




#====================================================================



def getArchPath( bugLev, omits, inDir, miscMap, relDirs, archPaths):
  inDir = os.path.normpath( inDir)
  if not os.path.isdir( inDir): throwerr('not a dir')

  # Check for omit matches
  keepIt = True
  for pattern in omits:
    if re.search( pattern, inDir): keepIt = False

  if keepIt:
    processDir( bugLev, inDir, miscMap, relDirs, archPaths)

    # Recurse to subdirs
    subNames = os.listdir( inDir)
    subNames.sort()
    for subName in subNames:
      subPath = os.path.join( inDir, subName)
      if os.path.isdir( subPath):
        getArchPath( bugLev, omits, subPath, miscMap, relDirs, archPaths)

  else:
    print 'wrapUpload: %-14s %s' % ('skip subTree', inDir,)


#====================================================================

def processDir( bugLev, inDir, miscMap, relDirs, archPaths):
  inDir = os.path.normpath( inDir)
  if not os.path.isdir( inDir): throwerr('not a dir')
  subNames = os.listdir( inDir)
  subNames.sort()

  # Check for requireNames and inc counts in miscMap
  numRequire = len( requireNames)
  numMatch = 0                 # num matches found in requireNames
  foundFlags = []              # parallel with requireNames
  for nm in requireNames:
    subPath = os.path.join( inDir, nm)
    if os.path.isfile( subPath):
      checkFileFull( subPath)
      numMatch += 1
      found = True
      miscMap['fnd_'+nm] += 1
    else: found = False
    foundFlags.append( found)

  if numMatch == 0:
    print 'wrapUpload: %-14s %s' % ('skip dir', inDir,)

  elif numMatch < len( requireNames):
    print ''
    print 'wrapUpload: Warning: incomplete dir: %s' % (inDir,)
    for ii in range(len(requireNames)):
      if foundFlags[ii]: print '  found:   %s' % (requireNames[ii],)
      else:              print '  MISSING: %s' % (requireNames[ii],)
    print ''
    miscMap['numWarn'] += 1

  elif numMatch == len(requireNames):

    # Append file paths to archPaths.
    for nm in requireNames:
      subPath = os.path.join( inDir, nm)
      archPaths.append( subPath)

    # Check for optionNames
    for nm in subNames:
      subPath = os.path.join( inDir, nm)
      if nm in optionNames and os.path.isfile( subPath):
        checkFile( subPath)
        archPaths.append( subPath)

    # Create smallMapFile in this dir
    writeDirDigest( bugLev, inDir)
    archPaths.append( os.path.join( inDir, smallMapFile))
    print 'wrapUpload: %-14s %s' % ('keep dir', inDir,)

    relDirs.append( inDir)

  else: throwerr('invalid numMatch')


#====================================================================

# Calls os.stat on fpath and returns map: statInfoName -> value

def getStatMap( bugLev, fpath):
  absName = os.path.abspath( fpath)
  statInfo = os.stat( absName)
  if bugLev >= 5:
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
# for a directory tree.
# Appends to statInfos, which is a list of pairs: [absName, statinfoMap].

def getStatInfos( bugLev, fname, statInfos):

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

# Create smallMapFile in this dir

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

  # Save the info from the path name and statInfo
  smallMap = {
    'icsdNum'   : icsdNum,
    'magType'   : magType,
    'magNum'    : magNum,
    'relaxType' : relaxType,
    'relaxNum'  : relaxNum,
    'absPath'   : absPath,
    'relPath'   : inDir,
    'statMap'   : statMap,
  }

  # Write smallMap to wrapUpload.data
  jFile = os.path.join( inDir, smallMapFile)
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
  reqCommaNames = ['standards', 'keywords',]

  # Required metadata text fields
  reqTextNames = [ 'firstName', 'lastName', 'publication', 'notes',]

  # Optional text fields
  optTextLists = [ 'omit',]

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
      value = mat.group(2)

      # Scan for the end of the value -- until the next comment or field
      iline += 1
      while iline < len(lines):
        line = lines[iline]
        if line.startswith('#') or re.match(r'^:(\w+):(.*)', line): break
        value += line        # lines already include \n
        iline += 1

      # Clean up whitespace at the ends, not within the value
      value = value.strip()

      if field in reqCommaNames:
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
        if metaMap.has_key(field):
          metaMap[field] += value            # append lists
        else: metaMap[field] = value

      elif field in reqTextNames:
        if metaMap.has_key(field):
          metaMap[field] += '\n' + value     # append text
        else: metaMap[field] = value

      elif field in optTextLists:
        if len(field) > 0:                   # ignore blank lines
          if metaMap.has_key(field):
            metaMap[field] += [value]        # append lists
          else: metaMap[field] = [value]     # make list

      else:
        throwerr('unknown field: \"%s\"  approx iline: %d  file: \"%s\"' \
          % (field, iline, fpath,))

  for nm in optTextLists:
    if not metaMap.has_key(nm): metaMap[nm] = []

  for nm in reqCommaNames + reqTextNames:
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
