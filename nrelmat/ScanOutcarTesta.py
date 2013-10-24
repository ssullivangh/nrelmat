#!/usr/bin/env python

import os, re, sys
import readVasp
import ScanOutcar
import numpy as np

#====================================================================


def badparms( msg):
  print '\nError: %s' % (msg,)
  print 'Parms:'
  print '  -bugLev    <int>      debug level'
  print '  -readType  <string>   outcar / xml'
  print '  -inDir     <string>   dir containing input OUTCAR or vasprun.xml'
  print ''
  sys.exit(1)

#====================================================================


def main():
  '''
  Test driver: Extracts info from the output of a VASP run.

  Command line parameters:

  ================  =========    ==============================================
  Parameter         Type         Description
  ================  =========    ==============================================
  **-bugLev**       integer      Debug level.  Normally 0.
  **-inDir**        string       Input directory containing OUTCAR
                                 and/or vasprun.xml.
  ================  =========    ==============================================
  '''

  bugLev = 0
  readType = None
  inDir = None

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if key == '-bugLev': bugLev = int( val)
    elif key == '-readType': readType = val
    elif key == '-inDir': inDir = val
    else: badparms('unknown key: "%s"' % (key,))

  if bugLev == None: badparms('parm not specified: -bugLev')
  if readType == None: badparms('parm not specified: -readType')
  if inDir == None: badparms('parm not specified: -inDir')

  rmap = readVasp.parseDir( bugLev, readType, inDir, -1)  # print = -1

  fpath = os.path.join( inDir, 'OUTCAR')
  scanner = ScanOutcar.ScanOutcar( bugLev, fpath)
  smap = scanner.scan()

  # Compare rmap and smap, key for key
  rkeys = rmap.__dict__.keys()
  rkeys.sort()
  skeys = smap.__dict__.keys()
  skeys.sort()

  irr = 0      # index into rkeys
  iss = 0      # index into skeys
  while True:
    if irr >= len( rkeys) and iss >= len( skeys): break
    elif irr >= len( rkeys):
      print '\nTesta: Unique S:'
      print 'skey: %s  val: %s' % (skeys[iss], smap.__dict__[skeys[iss]],)
      iss += 1
    elif iss >= len( skeys):
      print '\nTesta: Unique R:'
      print 'rkey: %s  val: %s' % (rkeys[irr], rmap.__dict__[rkeys[irr]],)
      irr += 1
    else:
      rkey = rkeys[irr]
      skey = skeys[iss]
      rval = rmap.__dict__[rkey]
      sval = smap.__dict__[skey]
      if rkey == skey:
        epsilon = 5.e-5
        compMsg = deepCompare( epsilon, rval, sval)
        if compMsg == None:
          print '\nTesta: Match:'
          print 'rkey: %s  val: %s' % (rkey, rval,)
        else:
          print '\nTesta: Mismatch: %s' % (compMsg,)
          print 'rkey: %s  val: %s' % (rkey, rval,)
          print 'skey: %s  val: %s' % (skey, sval,)
        irr += 1
        iss += 1
      elif rkey < skey:
        print '\nTesta: Unique R:'
        print 'rkey: %s  val: %s' % (rkey, rval,)
        irr += 1
      else:
        print '\nTesta: Unique S:'
        print 'skey: %s  val: %s' % (skey, sval)
        iss += 1



#====================================================================

def fixType( val):
  tpa = type(val).__name__
  if tpa == 'float64': val = float( val)
  elif tpa == 'int64': val = int( val)
  elif tpa == 'string_': val = str( val)
  elif tpa == 'list': val = np.array( val)
  return val


#====================================================================


def deepCompare( epsilon, va, vb):
  res = None

  va = fixType( va)
  vb = fixType( vb)

  tpa = type(va).__name__
  tpb = type(vb).__name__

  if tpa != tpb:
    res = 'types differ: %s vs %s' % ( tpa, tpb,)

  elif tpa == 'list':
    if len(va) != len(vb):
      res = 'len mismatch: %d vs %d' % (len(va), len(vb),)
    else:
      for ii in range(len(va)):
        res = deepCompare( epsilon, va[ii], vb[ii])
        if res != None: break

  elif tpa == 'ndarray':
    if va.shape != vb.shape:
      res = 'shape mismatch: %s vs %s' % (va.shape, vb.shape,)
    else:
      fa = va.flatten()
      fb = vb.flatten()
      for ii in range( fa.size):
        res = deepCompare( epsilon, fa[ii], fb[ii])
        if res != None: break

  elif type(va).__name__ == 'float':
    if abs( va - vb) > epsilon:
      res = 'float value mismatch: %g vs %g  vb-va: %g  (vb-va)/va: %g' \
        % (va, vb, vb - va, (vb - va) / va)

  elif type(va).__name__ in [ 'datetime', 'int', 'str']:
    if va != vb:
      res = 'scalar value mismatch: %s vs %s' % (repr(va), repr(vb),)

  else: throwerr('unknown type: %s' % (type(va).__name__,))


  return res

#====================================================================

def throwerr( msg):
  fullMsg = '%s\n' % (msg,)
  raise Exception( fullMsg)



#====================================================================

if __name__ == '__main__': main()

#====================================================================

