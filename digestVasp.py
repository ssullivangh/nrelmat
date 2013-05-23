#!/usr/bin/env python


import datetime, math, os, re, sys, time, traceback, cPickle

import readVasp


buglev = 0  # xxx make a parm

#====================================================================


def badparms( msg):
  print '\nError: %s' % (msg,)
  print 'Parms:'
  print '  -buglev     <int>      debug level'
  print '  -func       <string>   fillOne / fillTree'
  print '  -readType   <string>   xml / pylada'
  print '  -inDir      <string>   input file or dir'
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
  **-buglev**      integer      Debug level.  Normally 0.
  **-func**        string       Function.  See below.
  **-readType**    string       Xml or pylada.  See below.
  **-inDir**       string       Input directory.
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

  buglev = None
  func = None
  readType = None
  inDir = None
  outDigest = None

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if   key == '-buglev': buglev = int( val)
    elif key == '-func': func = val
    elif key == '-readType': readType = val
    elif key == '-inDir': inDir = val
    elif key == '-outDigest': outDigest = val
    else: badparms('unknown key: "%s"' % (key,))

  if buglev == None: badparms('parm not specified: -buglev')
  if func == None: badparms('parm not specified: -func')
  if readType == None: badparms('parm not specified: -readType')
  if inDir == None: badparms('parm not specified: -inDir')
  if outDigest == None: badparms('parm not specified: -outDigest')

  resList = []

  if func == 'fillOne':
    if buglev >= 1: logit('digestVasp: begin inDir: %s' % (inDir,))
    resObj = readVasp.parseDir( buglev, readType, inDir, -1)  # maxLev = -1
    resList.append( resObj)
  elif func == 'fillTree':
    fillTree( buglev, func, readType, inDir, resList)
  else: throwerr('unknown func: "%s"' % (func,))

  with open( outDigest, 'w') as fout:
    cPickle.dump( resList, fout, protocol=0)

#====================================================================


def fillTree(
  buglev,
  func,
  readType,
  inDir,
  resList):

  if buglev >= 2: logit('digestVasp: begin tree: %s' % (inDir,))
  fnames = os.listdir( inDir)
  fnames.sort()

  if readType == 'xml' and 'vasprun.xml' in fnames \
    or readType == 'pylada' and 'OUTCAR' in fnames:
    if buglev >= 1: logit('digestVasp: begin inDir: %s' % (inDir,))
    resObj = readVasp.parseDir( buglev, readType, inDir, -1)  # maxLev = -1
    resList.append( resObj)

  for fnm in fnames:
    fpath = inDir + '/' + fnm
    if os.path.isdir( fpath):
      fillTree(                     # recursion
        buglev,
        func,
        readType,
        fpath,
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

