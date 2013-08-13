#!/usr/bin/env python


import datetime, math, os, re, sys, time, cPickle

import readVasp


#====================================================================


def badparms( msg):
  print '\nError: %s' % (msg,)
  print 'Parms:'
  print '  -bugLev     <int>      debug level'
  print '  -func       <string>   fillOne / fillTree'
  print '  -readType   <string>   xml / pylada'
  print '  -inDir      <string>   input file or dir'
  print '  -omits      <string>   comma separated list of strings which, if'
  print '                         in a dir path, causes dir to be omitted.'
  print '  -outDigest  <string>   output digest file, to be used as'
  print '                           input by fillDbVasp.py.'
  sys.exit(1)


#====================================================================


def main():
  '''
  Read a VASP output file or tree and write a digest file.
  The function is determined by the **-func** parameter; see below.

  This function is called by wrapUpload.sh.
  This function calls readVasp.py.
  The resulting digest file is read later by wrapReceive.py.

  Command line parameters:

  ==============   =========    ==============================================
  Parameter        Type         Description
  ==============   =========    ==============================================
  **-bugLev**      integer      Debug level.  Normally 0.
  **-func**        string       Function.  See below.
  **-readType**    string       Xml or pylada.  See below.
  **-inDir**       string       Input directory.
  **-omits**       string       comma separated list of strings which, if
                                in a dir path, causes dir to be omitted.
  **-outDigest**   string       Output digest file.  Typically "digest.pkl".
  ==============   =========    ==============================================

  **Values for the -func Parameter:**

  **fillOne**
    Read the VASP output files in a single directory.

  **fillTree**
    Read the VASP output files in an entire directory tree.

  **Values for the -readType Parameter:**

  **xml**
    Read the vasprun.xml file.

  **pylada**
    Read the OUTCAR file.
  '''

  bugLev = None
  func = None
  readType = None
  inDir = None
  omits = []
  outDigest = None

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if   key == '-bugLev': bugLev = int( val)
    elif key == '-func': func = val
    elif key == '-readType': readType = val
    elif key == '-inDir': inDir = val
    elif key == '-omits':
      omits = val.strip().split(',')
      if len(omits) == 0: badparms('omits len is 0')
      for omit in omits:
        if len(omit) == 0: badparms('invalid omits')
    elif key == '-outDigest': outDigest = val
    else: badparms('unknown key: "%s"' % (key,))

  if bugLev == None: badparms('parm not specified: -bugLev')
  if func == None: badparms('parm not specified: -func')
  if readType == None: badparms('parm not specified: -readType')
  if inDir == None: badparms('parm not specified: -inDir')
  if outDigest == None: badparms('parm not specified: -outDigest')

  resList = []

  if func == 'fillOne':
    if bugLev >= 1: logit('digestVasp: begin inDir: %s' % (inDir,))
    foundOmit = False
    for omit in omits:
      if inDir.find(omit) >= 0: foundOmit = True
    if foundOmit:
      logit('digestVasp: omit inDir: %s' % (inDir,))
    else:
      resObj = readVasp.parseDir( bugLev, readType, inDir, -1)  # maxLev = -1
      resList.append( resObj)
  elif func == 'fillTree':
    fillTree( bugLev, func, readType, inDir, omits, resList)
  else: throwerr('unknown func: "%s"' % (func,))

  with open( outDigest, 'w') as fout:
    cPickle.dump( resList, fout, protocol=0)

#====================================================================


def fillTree(
  bugLev,
  func,
  readType,
  inDir,
  omits,
  resList):

  if bugLev >= 2: logit('digestVasp: begin tree: %s' % (inDir,))
  fnames = os.listdir( inDir)
  fnames.sort()

  if readType == 'xml' and 'vasprun.xml' in fnames \
    or readType == 'pylada' and 'OUTCAR' in fnames:
    if bugLev >= 1: logit('digestVasp: begin inDir: %s' % (inDir,))

    foundOmit = False
    for omit in omits:
      if inDir.find(omit) >= 0: foundOmit = True
    if foundOmit:
      logit('digestVasp: omit inDir: %s' % (inDir,))
    else:
      resObj = readVasp.parseDir( bugLev, readType, inDir, -1)  # maxLev = -1
      resList.append( resObj)

  for fnm in fnames:
    fpath = inDir + '/' + fnm
    if os.path.isdir( fpath):
      fillTree(                     # recursion
        bugLev,
        func,
        readType,
        fpath,
        omits,
        resList)


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
  print msg
  print >> sys.stderr, msg
  raise Exception( msg)

#====================================================================

if __name__ == '__main__': main()

#====================================================================

