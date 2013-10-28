#!/usr/bin/env python
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


import datetime, re, sys, traceback, os.path
import xml.etree.cElementTree as etree
import numpy as np
import pylada.vasp        # used by parsePylada tor parse OUTCAR files
import ScanXml            # used to parse vasprun.xml files
import ScanOutcar         # used to parse OUTCAR files



#====================================================================

class ResClass:
  '''
  An empty class used as a data container for parseDir results.

  The parseDir function will call either parsePylada or parseXml,
  and they will save the VASP results as attributes of
  an instance of ResClass.
  '''

  def __str__(self):
    keys = self.__dict__.keys()
    keys.sort()
    msg = ''
    for key in keys:
      val = self.__dict__[key]
      stg = str( val)
      if stg.find('\n') >= 0: sep = '\n'
      else: sep = ' '
      msg += '  %s:  type: %s  val:%s%s\n' % (key, type(val), sep, val,)
    return msg

#====================================================================


def badparms( msg):
  print '\nError: %s' % (msg,)
  print 'Parms:'
  print '  -bugLev    <int>      debug level'
  print '  -readType  <string>   outcar / xml'
  print '  -inDir     <string>   dir containing input OUTCAR or vasprun.xml'
  print '  -maxLev    <int>      max levels to print for xml'
  print ''
  print 'Examples:'
  print './readVasp.py -bugLev 5   -readType xml   -inDir tda/testlada.2013.04.15.fe.len.3.20/icsd_044729/icsd_044729.cif/hs-anti-ferro-0/relax_cellshape/0   -maxLev 0'
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
  **-readType**     string       If 'outcar', read the OUTCAR file.
                                 Else if 'xml', read the vasprun.xml file.
  **-inDir**        string       Input directory containing OUTCAR
                                 and/or vasprun.xml.
  **-maxLev**       int          Max number of levels to print for xml
  ================  =========    ==============================================
  '''

  bugLev = 0
  readType = None
  inDir = None
  maxLev = None

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if key == '-bugLev': bugLev = int( val)
    elif key == '-readType': readType = val
    elif key == '-inDir': inDir = val
    elif key == '-maxLev': maxLev = int( val)
    else: badparms('unknown key: "%s"' % (key,))

  if bugLev == None: badparms('parm not specified: -bugLev')
  if readType == None: badparms('parm not specified: -readType')
  if inDir == None: badparms('parm not specified: -inDir')
  if maxLev == None: badparms('parm not specified: -maxLev')

  ##np.set_printoptions( threshold=10000)

  resObj = parseDir( bugLev, readType, inDir, maxLev)

  print '\nmain: resObj:\n%s' % (resObj,)

  np.set_printoptions(threshold='nan')
  np.set_printoptions(linewidth=80)

  print '\n===== main: final resObj =====\n'
  print ''
  print 'import datetime'
  print 'import numpy as np'
  print ''
  keys = resObj.__dict__.keys()
  keys.sort()
  msg = ''
  for key in keys:
    val = resObj.__dict__[key]
    stg = repr(val)
    if type(val).__name__ == 'ndarray':
      print ''
      print '# %s shape: %s' % (key, val.shape,)
      stg = 'np.' + stg
    print '%s = %s' % (key, stg,)

#====================================================================


# Returns ResClass instance.
# If all is ok, we return a ResClass instance with
#   resObj.excMsg = None
#   resObj.excTrace = None
# Else we return a ResClass instance with
#   resObj.excMsg = exception message
#   resObj.excTrace = exception traceback

def parseDir(
  bugLev,
  readType,
  inDir,
  maxLev):
  '''
  Extracts info from the output of a VASP run.

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.
  * readType (str): If 'outcar', read the OUTCAR file.
    Else if 'xml', read the vasprun.xml file.
  * inDir (str): Input directory containing OUTCAR
    and/or vasprun.xml.
  * max (int) Max number of levels to print for xml

  **Returns**:

  * resObj (class ResClass): data object with attributes set.
  '''

  if not os.path.isdir(inDir):
    throwerr('inDir is not a dir: "%s"' % (inDir,))

  resObj = ResClass()
  resObj.excMsg = None
  resObj.excTrace = None

  try:
    if readType == 'xml':
      inFile = os.path.join( inDir, 'vasprun.xml')
      if not os.path.isfile(inFile):
        throwerr('inFile is not a file: "%s"' % (inFile,))
      ScanXml.parseXml( bugLev, inFile, maxLev, resObj)   # fills resObj
    elif readType in [ 'outcar', 'pylada']:
      if readType == 'outcar':
        scanner = ScanOutcar.ScanOutcar( bugLev, inDir, resObj)  # fills resObj
      else:    # else 'pylada'
        parsePylada( bugLev, inFile, resObj)   # fills resObj
    else: throwerr('unknown readType: %s' % (readType,))

  except Exception, exc:
    resObj.excMsg = repr(exc)
    resObj.excTrace = traceback.format_exc( limit=None)
    print 'readVasp.py.  caught exc: %s' % (resObj.excMsg,)
    print '  readType:   "%s"' % (readType,)
    print '  inDir:    "%s"' % (inDir,)
    print '===== traceback start ====='
    print resObj.excTrace
    print '===== traceback end ====='

  return resObj

#====================================================================

def parsePylada( bugLev, inFile, resObj):
  '''
  Extracts info from the OUTCAR file from a VASP run,
  using the PyLada vasp.Extract API.

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.
  * inFile (str): Path of the input OUTCAR file.
  * resObj (class ResClass): data object: we set attributes here.

  **Returns**:

  * None
  '''

  ex = pylada.vasp.Extract( inFile)
  if not ex.success: throwerr('file %s is not complete' % (inFile,))

  #===== program, version, date etc =====
  resObj.runDate      = ex.datetime

  # iterTimes are pairs: [cpuTime, realTime]
  resObj.iterCpuTimes   = [pair[0] for pair in ex.iterTimes]
  resObj.iterRealTimes  = [pair[1] for pair in ex.iterTimes]
  resObj.iterTotalTime = np.sum( resObj.iterRealTimes)

  #===== incar parameters =====
  # Use float() to get rid of Quantities units
  resObj.algo         = ex.algo
  resObj.ediff        = float( ex.ediff)
  resObj.encut_ev     = float( ex.encut)          # eV
  resObj.ibrion       = ex.ibrion
  resObj.isif         = ex.isif
  resObj.systemName   = ex.system
  #===== general parameters =====
  #===== electronic parameters =====
  resObj.ialgo        = ex.ialgo
  resObj.numBand      = ex.nbands
  resObj.numElectron  = ex.nelect
  resObj.icharg       = ex.icharg
  resObj.numSpin      = ex.ispin


  #===== atom info =====
  resObj.typeNames    = np.array( ex.species, dtype=str)
  resObj.typeNums     = np.array( ex.stoichiometry, dtype=int)
  resObj.typeValences = np.array( ex.ionic_charges, dtype=float)

  # totalValence = sum( count[i] * valence[i])
  # PyLada calls this valence.
  resObj.totalValence = np.dot( resObj.typeNums, resObj.typeValences)
  if bugLev >= 5: print 'totalValence: %g' % (resObj.totalValence,)
  if resObj.numElectron != resObj.totalValence:
    # xxx should this be an error?
    print('%g == numElectron != totalValence == %g' \
      % (resObj.numElectron, resObj.totalValence,))

  struct = ex.structure
  natom = len( struct)
  resObj.atomNames = [ struct[ii].type for ii in range( natom)]

  resObj.atomMasses_amu = None      # not available
  resObj.atomPseudos = None         # not available
  resObj.atomValences = None        # not available

  # atomPseudos: only the first title is available
  # atomMass, Valence: not available

  # partial_charges and magnetization are not available in xml
  # resObj.partialChargeMat = ex.partial_charges
  # resObj.magnetizationMat = ex.magnetization

  #===== initial structure =====
  # In structure.cell, the basis vectors are columns.
  # Change to rows.
  resObj.initialBasisMat = ex.initial_structure.cell.T
  resObj.initialRecipBasisMat = None  # not available

  struct = ex.initial_structure
  natom = len( struct)
  cartPos = natom * [None]
  for ii in range( natom):
    cartPos[ii] = struct[ii].pos      # no units

  resObj.initialCartPosMat = np.array( cartPos)

  resObj.initialFracPosMat = np.dot(
    resObj.initialCartPosMat, np.linalg.inv( resObj.initialBasisMat))

  #===== final structure =====
  # In structure.cell, the basis vectors are columns.
  # Change to rows.
  resObj.finalBasisMat = ex.structure.cell.T

  struct = ex.structure
  natom = len( struct)
  cartPos = natom * [None]
  for ii in range( natom):
    cartPos[ii] = struct[ii].pos

  resObj.finalCartPosMat = np.array( cartPos)

  resObj.finalFracPosMat = np.dot(
    resObj.finalCartPosMat, np.linalg.inv( resObj.finalBasisMat))

  #===== kpoints =====
  resObj.kpointCartMat = ex.kpoints    # transform
  resObj.numKpoint = resObj.kpointCartMat.shape[0]
  resObj.kpointWeights = None          # xxx not available

  #resObj.kpointFracMat = np.dot(
  #  resObj.kpointCartMat, np.linalg.inv( resObj.initialRecipBasisMat))
  # initialRecipBasisMat is not available, so
  resObj.kpointFracMat = None

  if bugLev >= 5:
    print 'numKpoint: %g' % (resObj.numKpoint,)
    print 'kpointFracMat:\n%s' % (repr(resObj.kpointFracMat),)
    print 'kpointCartMat:\n%s' % (repr(resObj.kpointCartMat),)
  #===== final volume and density =====
  resObj.finalVolume_ang3 = float( ex.volume)         # Angstrom^3
  resObj.recipVolume = float( ex.reciprocal_volume)
  resObj.finalDensity_g_cm3 = float( ex.density)      # g/cm3
  #===== last calc forces =====
  resObj.finalForceMat_ev_ang = np.array( ex.forces)  # eV/angstrom
  resObj.finalStressMat_kbar = np.array( ex.stress)   # kbar
  resObj.finalPressure_kbar = float( ex.pressure)     # kbar
  #===== eigenvalues and occupancies =====
  resObj.eigenMat = np.array( ex.eigenvalues)
  # Caution: for non-magnetic (numSpin==1),
  #   OUTCAR has occupMat values = 2, while vasprun.xml has values = 1.
  # For magnetic (numSpin==2), both OUTCAR and vasprun.xml have 1.
  resObj.occupMat = np.array( ex.occupations)
  #===== misc junk =====
  #===== energy, efermi0 =====
  resObj.energyNoEntrp = float( ex.total_energy)         # eV
  resObj.efermi0      = float( ex.fermi0K)               # eV
  #===== cbMin, vbMax, bandgap =====
  resObj.cbMin        = float( ex.cbm)                   # eV
  resObj.vbMax        = float( ex.vbm)                   # eV
  resObj.bandgap      = resObj.cbMin - resObj.vbMax      # eV
  if bugLev >= 5:
    print 'cbMin: %g' % (resObj.cbMin,)
    print 'vbMax: %g' % (resObj.vbMax,)
    print 'bandgap:  %g' % (resObj.bandgap,)

  resObj.cbms         = None                  # not available
  resObj.vbms         = None                  # not available
  resObj.cbmKpis      = None                  # not available
  resObj.vbmKpis      = None                  # not available
  resObj.bandgapa     = None                  # not available
  resObj.bandgaps     = None                  # not available

  return

# xxx to do:
#   energy               == totalEnergy
#   energy_sigma0        totalEnergySigma0
#   fermi0K              fermi0
#   fermi_energy         fermiEnergy
#   total_energy         totalEnergy
# array(-13.916343) * eV

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

  print msg
  print >> sys.stderr, msg
  raise Exception( msg)

#====================================================================

if __name__ == '__main__': main()

#====================================================================

