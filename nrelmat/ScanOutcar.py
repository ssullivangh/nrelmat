#!/usr/bin/env python

import datetime, os, re, sys
import numpy as np


#====================================================================
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
#====================================================================

class Sspec:
  def __init__( self, tag, pat, which, numMin, numMax, tp):
    self.tag = tag
    self.pat = pat
    self.which = which
    self.numMin = numMin
    self.numMax = numMax
    self.tp = tp

    if not (self.pat.startswith('^') and self.pat.endswith('$')):
      self.throwerr('invalid spec: %s' % (self,), None)
    if which not in ['first', 'last']:
      self.throwerr('invalid spec: %s' % (self,), None)
    if tp not in [ int, float]:
      self.throwerr('invalid spec: %s' % (self,), None)

    self.regex = re.compile( pat)

  def __str__( self):
    res = 'tag: %s  pat: %s  which: %s  numMin: %d  numMax: %d  tp: %s' \
      % (self.tag, repr( self.pat), self.which,
        self.numMin, self.numMax, self.tp,)
    return res


#====================================================================
#====================================================================


class ScanOutcar:


  def __init__( self, bugLev, fname):
    self.bugLev = bugLev
    self.fname = fname
    with open( fname) as fin:
      self.lines = fin.readlines()
    self.numLine = len( self.lines)
    # Strip all lines
    for ii in range( self.numLine):
      self.lines[ii] = self.lines[ii].strip()

  def scan( self):
    resObj = ResClass()

    self.getScalars( resObj)
    self.getDate( resObj)
    self.getTimes( resObj)
    self.getSystem( resObj)
    self.getTypeNames( resObj)
    self.getTypeNums( resObj)
    self.getBasisMats( resObj)
    self.getInitialPositions( resObj)
    self.getFinalPositionsForce( resObj)
    self.getStressMat( resObj)
    self.getTypeMassValence( resObj)
    self.getTypePseudos( resObj)
    self.getKpointMat( resObj)
    self.getEigenMat( resObj)

    self.calcMisc( resObj)
    self.calcEfermi( resObj)
    self.calcBandgaps( resObj)

    return resObj


#====================================================================

  def getScalars( self, resObj):
    nkpointPat = r'^k-points +NKPTS *= *(\d+) +k-points in BZ' \
      + r' +NKDIM *= *\d+ +number of bands +NBANDS *= *\d+$'
    nbandPat   = r'^k-points +NKPTS *= *\d+ +k-points in BZ' \
      + r' +NKDIM *= *\d+ +number of bands +NBANDS *= *(\d+)$'
    specs = [
      # EDIFF  = 0.6E-04   stopping-criterion for ELM
      Sspec( 'ediff', r'^EDIFF *= *([-.E0-9]+) *stopping-criterion.*$',
        'first', 1, 1, float),
      # ENCUT  =  340.0 eV  24.99 Ry    5.00 a.u. 4.51 4.51  4.51*2*pi/ulx,y,z
      Sspec( 'encut_ev', r'^ENCUT *= *([-.E0-9]+) eV .*$',
        'first', 1, 1, float),
      # IALGO  =     68    algorithm
      Sspec( 'ialgo', r'^IALGO *= *(\d+) +algorithm$',
        'first', 1, 1, int),
      # IBRION =      2    ionic relax: 0-MD 1-quasi-New 2-CG
      Sspec( 'ibrion', r'^IBRION *= *([-0-9]+) +ionic relax *: .*$',
        'first', 1, 1, int),
      # ICHARG =      0    charge: 1-file 2-atom 10-const
      Sspec( 'icharg', r'^ICHARG *= *(\d+) +charge *: .*$',
        'first', 1, 1, int),
      # ISPIN  =      2    # 1: non spin polarized,  2: spin polarized
      Sspec( 'numSpin', r'^ISPIN *= *(\d+) +spin polarized .*$',
        'first', 1, 1, int),
      # ISIF   =      3    stress and relaxation
      Sspec( 'isif', r'^ISIF *= *(\d+) +stress and relaxation$',
        'first', 1, 1, int),
      # NELECT =      14.0000    total number of electrons
      Sspec( 'numElectron',
        r'^NELECT *= *([-.E0-9]+) +total number of electrons$',
        'first', 1, 1, float),
      # k-points    NKPTS =    260   k-points in BZ     NKDIM =    260 \
      #   number of bands    NBANDS=     13
      Sspec( 'numKpoint', nkpointPat, 'first', 1, 1, int),
      Sspec( 'numBand',   nbandPat, 'first', 1, 1, int),
      # volume of cell :       20.0121
      Sspec( 'finalVolume_ang3', r'^volume of cell *: +([-.E0-9]+)$',
        'last', 1, 0, float),

      # Spacing varies:
      # energy without entropy =  -60.501550  energy(sigma->0) =  -60.501640
      # energy  without entropy=  -15.051005  energy(sigma->0) =  -15.051046
      Sspec( 'energyNoEntrp', 
        r'^energy +without +entropy *= *([-.E0-9]+)' \
          + r' +energy\(sigma->0\) *= *[-.E0-9]+$',
        'last', 1, 0, float),

      #   E-fermi :   6.5043     XC(G=0): -12.1737     alpha+bet :-11.7851
      Sspec( 'efermi', r'^E-fermi *: *([-.E0-9]+) +XC.*alpha\+bet.*$',
        'last', 1, 0, float),
    ] # specs

    for spec in specs:
      ixs = self.findLines( [spec.pat], spec.numMin, spec.numMax)
      if spec.which == 'first': ix = ixs[0]
      elif spec.which == 'last': ix = ixs[-1]
      else: self.throwerr('invalid which in spec: %s' % (spec,), None)
      mat = spec.regex.match( self.lines[ix])
      value = spec.tp( mat.group(1))
      resObj.__dict__[spec.tag] = value

      if self.bugLev >= 5:
        print 'getScalars: %s: %s' % (spec.tag, value,)


#====================================================================

  # runDate
  #   executed on             LinuxIFC date 2013.10.18  08:44:21
  def getDate( self, resObj):
    pat = r'^executed on .* date +\d{4}\.\d{2}\.\d{2} +\d{2}:\d{2}:\d{2}$'
    ixs = self.findLines( [pat], 1, 1)        # pats, numMin, numMax
    toks = self.lines[ixs[0]].split()
    stg = ' '.join( toks[-2:])
    resObj.runDate = datetime.datetime.strptime( stg, '%Y.%m.%d %H:%M:%S')

    if self.bugLev >= 5:
      print 'getDate: runDate: %s' % (
        resObj.runDate.strftime('%Y.%m.%d %H:%M:%S'),)

#====================================================================

  # iterCpuTimes
  # iterRealTimes
  # Lines are like either of:
  #   LOOP+:  cpu time   22.49: real time   24.43
  #   LOOP+:  VPU time   42.93: CPU time   43.04
  # In the second line, "VPU" means CPU, and "CPU" means wall time.
  # See: http://cms.mpi.univie.ac.at/vasp-forum/forum_viewtopic.php?3.336

  def getTimes( self, resObj):
    pat = r'^LOOP\+ *: +[a-zA-Z]+ +time +([.0-9]+): +[a-zA-Z]+' \
      + r' +time +([.0-9]+)$'
    ixs = self.findLines( [pat], 1, 0)        # pats, numMin, numMax

    cpuTimes = []
    realTimes = []
    for ix in ixs:
      mat = re.match( pat, self.lines[ix])
      cpuTimes.append( float( mat.group(1)))
      realTimes.append( float( mat.group(2)))
    resObj.iterCpuTimes = cpuTimes
    resObj.iterRealTimes = realTimes

    if self.bugLev >= 5:
      print 'getTimes: iterCpuTimes: %s' % (resObj.iterCpuTimes,)
      print 'getTimes: iterRealTimes: %s' % (resObj.iterRealTimes,)

#====================================================================

  # system
  #   SYSTEM =  icsd_633029 in icsd_633029.cif, hs-ferr
  def getSystem( self, resObj):
    pat = r'^SYSTEM *= '
    ixs = self.findLines( [pat], 1, 0)        # pats, numMin, numMax
    toks = self.lines[ixs[0]].split()
    nm = ' '.join(toks[2:])
    nm = nm.strip('\"\'')   # strip unpaired surrounding quotes
    resObj.systemName = nm

    if self.bugLev >= 5:
      print 'getSystem: systemName: %s' % (resObj.systemName,)

#====================================================================

  # typeNames == species
  # All lines like:
  #   VRHFIN =Fe:  d7 s1
  #   VRHFIN =O: s2p4
  # Other possible patterns:
  #   POTCAR:   PAW_PBE Zn 06Sep2000    # no, repeated
  #   TITEL  = PAW_PBE Zn 06Sep2000

  def getTypeNames( self, resObj):
    pat = r'^VRHFIN *= *([a-zA-Z]+): '
    regexa = re.compile( pat)
    typeNames = []
    for iline in range( self.numLine):
      line = self.lines[iline]
      mat = regexa.match( line)
      if mat != None:
        typeNames.append( mat.group( 1))
    resObj.typeNames = typeNames

    if self.bugLev >= 5:
      print 'getTypeNames: typeNames: %s' % (resObj.typeNames,)

#====================================================================

  # typeNums == stoichiometry
  #   ions per type =               1   1
  def getTypeNums( self, resObj):
    pat = r'^ions per type *= '
    ixs = self.findLines( [pat], 1, 1)        # pats, numMin, numMax
    toks = self.lines[ixs[0]].split()
    resObj.typeNums = map( int, toks[4:])
    resObj.numAtom = sum( resObj.typeNums)

    if self.bugLev >= 5:
      print 'getTypeNums: typeNums: %s' % (resObj.typeNums,)
      print 'getTypeNums: numAtom: %d' % (resObj.numAtom,)

#====================================================================

  # initialBasisMat, finalBasisMat == cell
  #   direct lattice vectors                 reciprocal lattice vectors
  #   0.0004124  2.1551750  2.1553184    -0.2320833  0.2320088  0.2320195
  #   2.1551376  0.0004322  2.1552987     0.2320129 -0.2320836  0.2320237
  #   2.1548955  2.1549131  0.0006743     0.2320650  0.2320652 -0.2320942
  def getBasisMats( self, resObj):
    pat = r'^direct lattice vectors +reciprocal lattice vectors$'
    ixs = self.findLines( [pat], 2, 0)        # pats, numMin, numMax

    ix = ixs[0]  # initial
    resObj.initialBasisMat = self.parseMatrix(
      6, ix+1, ix+4, 0, 3)       # ntok, rowBeg, rowEnd, colBeg, colEnd
    resObj.initialRecipBasisMat = self.parseMatrix(
      6, ix+1, ix+4, 3, 6)       # ntok, rowBeg, rowEnd, colBeg, colEnd

    ix = ixs[-1]  # final
    # In vasprun.xml and OUTCAR, the basis vectors are rows.
    resObj.finalBasisMat = self.parseMatrix(
      6, ix+1, ix+4, 0, 3)       # ntok, rowBeg, rowEnd, colBeg, colEnd
    resObj.finalRecipBasisMat = self.parseMatrix(
      6, ix+1, ix+4, 3, 6)       # ntok, rowBeg, rowEnd, colBeg, colEnd

    if self.bugLev >= 5:
      print 'getBasisMats: initialBasisMat:\n%s' \
        % (self.formatMatrix( resObj.initialBasisMat),)
      print 'getBasisMats: initialRecipBasisMat:\n%s' \
        % (self.formatMatrix( resObj.initialRecipBasisMat),)
      print 'getBasisMats: finalBasisMat:\n%s' \
        % (self.formatMatrix( resObj.finalBasisMat),)
      print 'getBasisMats: finalRecipBasisMat:\n%s' \
        % (self.formatMatrix( resObj.finalRecipBasisMat),)


#====================================================================

  # initialFracPosMat, initialCartPosMat
  #   position of ions in fractional coordinates (direct lattice)
  #     0.00000005  0.99999999  0.99999997
  #     0.49999995  0.50000001  0.50000003
  #
  #   position of ions in cartesian coordinates  (Angst):
  #     4.24342506  2.12183357  2.12263079
  #     2.12184258  2.12186596  2.12233823
  def getInitialPositions( self, resObj):
    patf = r'^position of ions in fractional coordinates \(direct lattice\)$'
    patc = r'^position of ions in cartesian coordinates +\(Angst\):$'

    ixs = self.findLines( [patf], 1, 1)  # pats, numMin, numMax
    ix = ixs[0]
    resObj.initialFracPosMat = self.parseMatrix(
      3, ix+1, ix+1+resObj.numAtom, 0, 3)
      # ntok, rowBeg, rowEnd, colBeg, colEnd

    ixs = self.findLines( [patc], 1, 1)  # pats, numMin, numMax
    ix = ixs[0]
    resObj.initialCartPosMat = self.parseMatrix(
      3, ix+1, ix+1+resObj.numAtom, 0, 3)
      # ntok, rowBeg, rowEnd, colBeg, colEnd

    # Just test the linear algebra
    test_initialFracPosMat = np.dot(
      resObj.initialCartPosMat, np.linalg.inv( resObj.initialBasisMat))
    test_initialCartPosMat = np.dot(
      resObj.initialFracPosMat, resObj.initialBasisMat)
    if not np.allclose(
      test_initialFracPosMat, resObj.initialFracPosMat, 0, 1.e-1):
      self.throwerr('initialFracMat mismatch', None)
    if not np.allclose(
      test_initialCartPosMat, resObj.initialCartPosMat, 0, 1.e-1):
      self.throwerr('initialCartMat mismatch', None)

    if self.bugLev >= 5:
      print 'getInitialPositions: initialFracPosMat:\n%s' \
        % (self.formatMatrix( resObj.initialFracPosMat),)
      print 'getInitialPositions: initialCartPosMat:\n%s' \
        % (self.formatMatrix( resObj.initialCartPosMat),)


#====================================================================

  # finalCartPosMat, forceMat
  #   POSITION                       TOTAL-FORCE (eV/Angst)
  #   ------------------------------------------------------------------
  #   0.59671  5.05062  2.21963       0.003680   -0.001241  -0.004039
  #   4.98024  2.21990  0.58287       -0.000814  -0.015091  -0.012495
  #   2.23430  0.66221  5.03287       0.017324   0.003318   -0.014394
  #   ...
  #   ------------------------------------------------------------------

  def getFinalPositionsForce( self, resObj):
    pat = r'^POSITION +TOTAL-FORCE \(eV/Angst\)$'
    ixs = self.findLines( [pat], 1, 0)     # pats, numMin, numMax
    ix = ixs[-1]    # last one
    resObj.finalCartPosMat = self.parseMatrix(
      6, ix+2, ix+2+resObj.numAtom, 0, 3)
      # ntok, rowBeg, rowEnd, colBeg, colEnd
    resObj.finalForceMat_ev_ang = self.parseMatrix(
      6, ix+2, ix+2+resObj.numAtom, 3, 6)
      # ntok, rowBeg, rowEnd, colBeg, colEnd

    resObj.finalFracPosMat = np.dot(
      resObj.finalCartPosMat, np.linalg.inv( resObj.finalBasisMat))

    if self.bugLev >= 5:
      print 'getFinalPositionsForce: finalCartPosMat:\n%s' \
        % (self.formatMatrix( resObj.finalCartPosMat),)
      print 'getFinalPositionsForce: finalFracPosMat:\n%s' \
        % (self.formatMatrix( resObj.finalFracPosMat),)
      print 'getFinalPositionsForce: finalForceMat_ev_ang:\n%s' \
        % (self.formatMatrix( resObj.finalForceMat_ev_ang),)

#====================================================================

  # stressMat
  #   FORCE on cell =-STRESS in cart. coord.  units (eV):
  #   Direction    XX         YY         ZZ        XY        YZ        ZX
  #   -----------------------------------------------------------------------
  #   Alpha Z    76.60341   76.60341   76.60341
  #   Ewald    -318.46783 -318.46428 -318.52959  -0.00310   0.03083   0.02783
  #   Hartree    63.38495   63.38593   63.35616   0.00114   0.01511   0.01368
  #   E(xc)     -70.45894  -70.45888  -70.45878  -0.00052  -0.00008  -0.00008
  #   Local       3.47019    3.46661    3.56011  -0.00319  -0.04620  -0.04172
  #   n-local    -6.52091   -6.52080   -6.52183  -0.00373  -0.00131  -0.00134
  #   augment    82.46862   82.46871   82.46910   0.00638   0.00129   0.00151
  #   Kinetic   170.67238  170.67209  170.67398   0.00710   0.00098   0.00116
  #   Fock        0.00000    0.00000    0.00000   0.00000   0.00000   0.00000
  #   -----------------------------------------------------------------------
  #   Total       1.15189    1.15278    1.15256   0.00410   0.00063   0.00105
  #   in kB      96.62361   96.69864   96.68018   0.34362   0.05255   0.08820
  #   external pressure =       96.67 kB  Pullay stress =        0.00 kB

  def getStressMat( self, resObj):
    pat = r'^FORCE on cell *= *-STRESS in cart. coord. +units \(eV\) *:$'
    ixs = self.findLines( [pat], 1, 0)        # pats, numMin, numMax
    ix = ixs[-1]    # last one

    # Find the "Total" and "in kB" lines
    evline = None
    kbline = None
    for ii in range(ix+1, ix + 16):
      line = self.lines[ii]
      if re.match(r'^Total( +[-.E0-9]+){6}$', line): evline = ii
      if re.match(r'^in kB( +[-.E0-9]+){6}$', line): kbline = ii
    if evline == None: self.throwerr('unknown stress ev', ix)
    if kbline == None: self.throwerr('unknown stress kb', ix)

    # Extract tokens from the "Total" and "in kB" lines
    evtoks = self.lines[ evline].split()[1:]  # skip 'Total'
    kbtoks = self.lines[ kbline].split()[2:]  # skip 'in kB'
    if len( evtoks) != 6: self.throwerr('unknown stress evtoks', evline)
    if len( kbtoks) != 6: self.throwerr('unknown stress kbtoks', kbline)
    evs = map( float, evtoks)
    kbs = map( float, kbtoks)

    # Create 3x3 matrices for ev and kb stress
    evstress = np.zeros( [3, 3], dtype=float)
    kbstress = np.zeros( [3, 3], dtype=float)
    # Add in the terms XX, YY, ZZ
    for ii in range(3):
      evstress[ii,ii] += evs[ii]
      kbstress[ii,ii] += kbs[ii]
    evstress[1,0] = evstress[0,1] = evs[3]    # XY
    kbstress[1,0] = kbstress[0,1] = kbs[3]    # XY
    evstress[2,0] = evstress[0,2] = evs[5]    # XY
    kbstress[2,0] = kbstress[0,2] = kbs[5]    # XY
    evstress[2,1] = evstress[1,2] = evs[4]    # YZ
    kbstress[2,1] = kbstress[1,2] = kbs[4]    # YZ

    resObj.finalStressMat_ev = evstress
    resObj.finalStressMat_kbar = kbstress
    resObj.finalPressure_kbar = kbstress.diagonal().sum() / 3.0

    if self.bugLev >= 5:
      print 'getStressMat: finalStressMat_ev:\n%s' \
        % (self.formatMatrix( resObj.finalStressMat_ev),)
      print 'getStressMat: finalStressMat_kbar:\n%s' \
        % (self.formatMatrix( resObj.finalStressMat_kbar),)
      print 'getStressMat: finalPressure_kbar: %s' \
        % (resObj.finalPressure_kbar,)

#====================================================================

  ## Old typeValences == ionic_charges
  ##    ZVAL   =   8.00  6.00
  #def getTypeValencesUnused( self, resObj):
  #  pat = r'^ZVAL *= '
  #  ixs = self.findLines( [pat], 1, 1)        # pats, numMin, numMax
  #  toks = self.lines[ixs[0]].split()
  #  resObj.typeValences = map( float, toks[2:])

#====================================================================

  # typeMasses, typeValences
  #   POMASS =   55.847; ZVAL   =    8.000    mass and valenz
  #   POMASS =   16.000; ZVAL   =    6.000    mass and valenz
  #   POMASS =  55.85 16.00  # ignore this
  #
  def getTypeMassValence( self, resObj):
    pat = r'^POMASS *= *([.0-9]+); +ZVAL += +([.0-9]+) +mass and valenz'
    ixs = self.findLines( [pat], 1, 0)        # pats, numMin, numMax
    typeMasses = []
    typeValences = []
    for ix in ixs:
      mat = re.match( pat, self.lines[ix])
      typeMasses.append( float( mat.group(1)))
      typeValences.append( float( mat.group(2)))
    resObj.typeMasses_amu = typeMasses
    resObj.typeValences = typeValences

    if self.bugLev >= 5:
      print 'getTypeMassValence: typeMasses_amu: %s' % (resObj.typeMasses_amu,)
      print 'getTypeMassValence: typeValences: %s' % (resObj.typeValences,)

#====================================================================

  # typePseudos
  #   TITEL  = PAW_PBE Fe 06Sep2000
  #   TITEL  = PAW_PBE O_s 07Sep2000
  def getTypePseudos( self, resObj):
    pat = r'^TITEL *= *(PAW.*)$'
    ixs = self.findLines( [pat], 1, 0)        # pats, numMin, numMax
    typePseudos = []
    for ix in ixs:
      mat = re.match( pat, self.lines[ix])
      typePseudos.append( mat.group(1).strip())
    resObj.typePseudos = typePseudos

    if self.bugLev >= 5:
      print 'getTypePseudos: typePseudos: %s' % (resObj.typePseudos,)

#====================================================================

  # kpointFracMat, kpointCartMat,
  # kpointMults, kpointWeights == normalized kpointMults
  #   Found    260 irreducible k-points:
  #   
  #   Following reciprocal coordinates:
  #              Coordinates               Weight
  #    0.000000  0.000000  0.000000      1.000000
  #    0.125000  0.000000  0.000000      2.000000
  #    0.250000  0.000000  0.000000      2.000000
  #    ...
  #    0.500000  0.500000  0.500000      1.000000
  #   
  #   Following cartesian coordinates:
  #              Coordinates               Weight
  #    0.000000  0.000000  0.000000      1.000000
  #   -0.029463  0.029454  0.029457      2.000000
  #   -0.058925  0.058909  0.058914      2.000000
  #    ...
  #    0.117822  0.117821  0.117795      1.000000
  #
  def getKpointMat( self, resObj):
    headPat  = r'^Found +\d+ +irreducible k-points *:$'
    blankPat = r'^$'
    recipPat = r'^Following reciprocal coordinates *:$'
    cartPat  = r'^Following cartesian coordinates *:$'
    wtPat    = r'^Coordinates +Weight$'
    numKpoint = resObj.numKpoint

    # xxx this is what vasprun.xml calls "kpoints"
    ixs = self.findLines(
      [headPat, blankPat, recipPat, wtPat], 0, 0)   # pats, numMin, numMax

    if len(ixs) == 1:           # if generated kpoints ...

      # Get generated reciprocol coords
      ix = ixs[0] + 4               # start of matrix
      kpMat = self.parseMatrix(     # kpoints and weights (multiplicities)
        4, ix, ix+numKpoint, 0, 4)  # ntok, rowBeg, rowEnd, colBeg, colEnd
      resObj.kpointFracMat = kpMat[ :, 0:3]

      kpMults = kpMat[ :, 3]
      resObj.kpointMults = kpMults
      resObj.kpointWeights = kpMults / float( kpMults.sum())

      # Get generated cartesian coords
      ixCart = ix + numKpoint + 1
      ixs = self.findLines( [cartPat, wtPat], 1, 1)   # pats, numMin, numMax
      if ixs[0] != ixCart: self.throwerr('kpoint format', ixCart)
      ix = ixCart + 2              # start of matrix
      kpMat = self.parseMatrix(    # kpoints and weights (multiplicities)
        4, ix, ix+numKpoint, 0, 4) # ntok, rowBeg, rowEnd, colBeg, colEnd
      resObj.kpointCartMat = kpMat[ :, 0:3]
      test_kpointMults = kpMat[ :, 3]
      if not np.allclose( test_kpointMults, resObj.kpointMults, 0, 1.e-5):
        self.throwerr('kpointMults mismatch', None)

    # Get the actual kpoints
    pat = r'^k-points in units of 2pi/SCALE and weight:$'
    ixs = self.findLines( [pat], 1, 1)    # pats, numMin, numMax
    ix = ixs[0] + 1
    kpMat = self.parseMatrix(     # kpoints and weights (multiplicities)
      4, ix, ix+numKpoint, 0, 4)  # ntok, rowBeg, rowEnd, colBeg, colEnd
    actual_kpointCartMat = kpMat[ :, 0:3]
    wts = kpMat[ :, 3]
    # Sometimes the wts are not normalized to 1, for example in
    #   icsd_633029.cif/non-magnetic/relax_cellshape/1
    # the sum is 1.024
    actual_kpointWeights = wts / sum( wts)
    actual_kpointFracMat = np.dot(
      actual_kpointCartMat, np.linalg.inv( resObj.initialRecipBasisMat))

    # Find kpoint multiplicities by multiplying kpointWeights
    # by the min value that makes them all integers
    uniqWts = list( set( wts))
    uniqWts.sort()
    minWt = uniqWts[0]
    factor = None
    for ii in range(1, 10):
      tfact = ii / float( minWt)
      allOk = True
      for wt in uniqWts:
        val = tfact * wt
        if abs( val - round(val)) > 1.e-5:
          allOk = False
          break
      if allOk:
        factor = tfact
        break
    if factor == None: self.throwerr('no kpointMults found', None)
    actual_kpointMults = wts * factor

    # If we got generated points, check that they == actuals.
    # If no generated points, use the actuals.
    if hasattr( resObj, 'kpointFracMat'):
      if not np.allclose(
        actual_kpointFracMat, resObj.kpointFracMat, 0, 1.e-5):
        self.throwerr('kpointFracMat mismatch', None)
      if not np.allclose(
        actual_kpointCartMat, resObj.kpointCartMat, 0, 1.e-5):
        self.throwerr('kpointCartMat mismatch', None)
      if not np.allclose(
        actual_kpointMults, resObj.kpointMults, 0, 1.e-5):
        self.throwerr('kpointMults mismatch', None)
      if not np.allclose(
        actual_kpointWeights, resObj.kpointWeights, 0, 1.e-5):
        self.throwerr('kpointWeights mismatch', None)
    else:
      resObj.kpointFracMat = actual_kpointFracMat
      resObj.kpointCartMat = actual_kpointCartMat
      resObj.kpointMults   = actual_kpointMults
      resObj.kpointWeights = actual_kpointWeights

    # Just test the linear algebra
    test_kpointFracMat = np.dot(
      resObj.kpointCartMat, np.linalg.inv( resObj.initialRecipBasisMat))
    test_kpointCartMat = np.dot(
      resObj.kpointFracMat, resObj.initialRecipBasisMat)
    if not np.allclose( test_kpointFracMat, resObj.kpointFracMat, 0, 1.e-5):
      self.throwerr('test_kpointFracMat mismatch', None)
    if not np.allclose( test_kpointCartMat, resObj.kpointCartMat, 0, 1.e-5):
      self.throwerr('test_kpointCartMat mismatch', None)

    if self.bugLev >= 5:
      print 'getKpointMat: kpointFracMat:\n%s' \
        % (self.formatMatrix( resObj.kpointFracMat),)
      print 'getKpointMat: kpointCartMat:\n%s' \
        % (self.formatMatrix( resObj.kpointCartMat),)
      print 'getKpointMat: kpointMults: %s' % (resObj.kpointMults,)
      print 'getKpointMat: kpointWeights: %s' % (resObj.kpointWeights,)
      print 'getKpointMat: numKpoint: %d' % (numKpoint,)
      print 'getKpointMat: kpointMults sum:  %g' \
        % (resObj.kpointMults.sum(),)
      print 'getKpointMat: kpointWeights sum:  %g' \
        % (resObj.kpointWeights.sum(),)

#====================================================================

  # eigenMat, occupMat
  #
  #   spin component 1          # this line is not in non-mag calcs
  #
  #   k-point   1 :       0.0000    0.0000    0.0000
  #    band No.  band energies     occupation
  #        1     -14.2072      1.00000
  #        2       2.5938      1.00000
  #       ...
  #       13      23.5652      0.00000
  #
  #   k-point   2 :       0.1250    0.0000    0.0000
  #    band No.  band energies     occupation
  #        1     -14.0551      1.00000
  #        2       1.3327      1.00000
  #       ...
  #       13      23.5652      0.00000
  #   ...
  #   k-point 260 :       0.5000    0.5000    0.5000
  #    band No.  band energies     occupation
  #        1     -13.0330      1.00000
  #        2      -2.2402      1.00000
  #       ...
  #       13      19.0910      0.00000
  #
  #   spin component 2
  #
  #   k-point   1 :       0.0000    0.0000    0.0000
  #    band No.  band energies     occupation
  #        1     -13.6767      1.00000
  #        2       3.2576      1.00000
  #   ...

  def getEigenMat( self, resObj):
    numSpin = resObj.numSpin
    numKpoint = resObj.numKpoint
    numBand = resObj.numBand

    compPat    = '^spin component [12]$'
    kpFirstPat = '^k-point +1 *: +[-.E0-9]+ +[-.E0-9]+ +[-.E0-9]+$'
    bandPat    = '^band No. +band energies +occupation$'

    # Do we have 'spin component' lines?
    compIxs = self.findLines( [compPat], 0, 0)     # pats, numMin, numMax
    eigenMat = np.zeros([ numSpin, numKpoint, numBand])
    occupMat = np.zeros([ numSpin, numKpoint, numBand])

    if len(compIxs) == 0:         # if no spin components ...
      if numSpin != 1: self.throwerr('numSpin mismatch', None)
    else:                         # else we have spin components ...
      if numSpin != 2: self.throwerr('numSpin mismatch', None)

    firstIxs = self.findLines( [kpFirstPat, bandPat], 1, 0)
    for isp in range( numSpin):
      istart = firstIxs[ -numSpin + isp]    # use the last
      for ikp in range( numKpoint):
        # Parse one k-point section, for numBand lines
        isection = istart + 2 + ikp * (3 + numBand)
        tmat = self.parseMatrix(
          3, isection, isection + numBand, 1, 3) # ntok, rBeg, rEnd, cBeg, cEnd
        eigenMat[ isp, ikp, 0:numBand] = tmat[ 0:numBand, 0]  # col 0: eigen
        occupMat[ isp, ikp, 0:numBand] = tmat[ 0:numBand, 1]  # col 1: occup

    resObj.eigenMat = eigenMat
    resObj.occupMat = occupMat

    if self.bugLev >= 5:
      for isp in range( resObj.numSpin):
        print 'getEigenMat: isp: %d  eigenMat:\n%s' \
          % (isp, self.formatMatrix( resObj.eigenMat[isp]),)
      for isp in range( resObj.numSpin):
        print 'getEigenMat: isp: %d  occupMat:\n%s' \
          % (isp, self.formatMatrix( resObj.occupMat[isp]),)

#====================================================================


  def calcMisc( self, resObj):

    resObj.iterTotalTime = sum( resObj.iterRealTimes)
    if self.bugLev >= 5:
      print 'calcMisc: iterTotalTime: %g' % (resObj.iterTotalTime,)


    algoMap = {
      2: 'Nothing',
      4: 'Subrot',
      38: 'Normal',
      48: 'Very Fast',
      53: 'Damped',
      58: 'Conjugate',
      68: 'Fast',
      90: 'Exact',
    }
    resObj.algo = algoMap[ resObj.ialgo]
    if self.bugLev >= 5:
      print 'calcMisc: algo: %s' % (resObj.algo,)


    atomMasses_amu = []
    atomNames = []
    atomPseudos = []
    atomValences = []
    for ii in range( len( resObj.typeNames)):
      atomMasses_amu += resObj.typeNums[ii] * [ resObj.typeMasses_amu[ii] ]
      atomNames += resObj.typeNums[ii] * [ resObj.typeNames[ii] ]
      atomPseudos += resObj.typeNums[ii] * [ resObj.typePseudos[ii] ]
      atomValences += resObj.typeNums[ii] * [ resObj.typeValences[ii] ]
    resObj.atomMasses_amu = atomMasses_amu
    resObj.atomNames = atomNames
    resObj.atomPseudos = atomPseudos
    resObj.atomValences = atomValences
    if self.bugLev >= 5:
      print 'calcMisc: atomMasses_amu: %s' % (resObj.atomMasses_amu,)
      print 'calcMisc: atomNames: %s' % (resObj.atomNames,)
      print 'calcMisc: atomPseudos: %s' % (resObj.atomPseudos,)
      print 'calcMisc: atomValences: %s' % (resObj.atomValences,)


    resObj.totalValence = np.dot( resObj.typeNums, resObj.typeValences)
    if self.bugLev >= 5:
      print 'calcMisc: totalValence: %s' % (resObj.totalValence,)


    # The scale is hard coded as 1.0 in PyLada crystal/read.py,
    # in both icsd_cif_a and icsd_cif_b.
    volScale = 1.0
    resObj.finalVolumeCalc_ang3 = abs( np.linalg.det(
      volScale * resObj.finalBasisMat))
    # xxx better: get atomic weights from periodic table
    volCm3 = resObj.finalVolumeCalc_ang3 / (1.e8)**3   # 10**8 Angstrom per cm
    totMass = np.dot( resObj.typeNums, resObj.typeMasses_amu)
    totMassGm = totMass *  1.660538921e-24        #  1.660538921e-24 g / amu
    resObj.finalDensity_g_cm3 = totMassGm / volCm3
    # xxx compare with resObj.finalVolume_ang3
    if self.bugLev >= 5:
      print 'calcMisc: typeNums: %s' % (resObj.typeNums,)
      print 'calcMisc: typeMasses_amu: %s' % (resObj.typeMasses_amu,)
      print 'calcMisc: totMass: %s' % (totMass,)
      print 'calcMisc: totMassGm: %s' % (totMassGm,)
      print 'calcMisc: volCm3: %s' % (volCm3,)
      print 'calcMisc: finalVolumeCalc_ang3: %s' \
        % (resObj.finalVolumeCalc_ang3,)
      print 'calcMisc: finalDensity_g_cm3: %s' \
        % (resObj.finalDensity_g_cm3,)

    # reciprocal space volume, * (2*pi)**3
    # As in PyLada.
    invMat = np.linalg.inv( volScale * resObj.finalBasisMat)
    resObj.recipVolume = abs( np.linalg.det( invMat)) * (2 * np.pi)**3


#====================================================================

  def calcEfermi( self, resObj):

    # efermiCalc
    # Make an array allEigs of all the eigenvalues for all the
    # kpoints, with each eigenvalue replicated by the associated
    # kpoint weight.
    # Further, if ispin == 1 (non spin polarized),
    # replicate each eigenvalue again.
    #
    # Sort allEigs by increasing value.
    # Let factor =
    #   if numSpin == 1: 2/sum(weights)    # non spin polarized
    #   if numSpin == 2: 1/sum(weights)    # spin polarized
    # Start summing: occ = factor * (index into allEigs).
    # When occ = totalValence, the corresponding eigVal is fermi0K.

    numSpin = resObj.numSpin
    numKpoint = resObj.numKpoint
    numBand = resObj.numBand

    # xxx check all this
    numEig = 0
    for ikp in range( numKpoint):
      numEig += numBand * resObj.kpointMults[ikp]
      print 'xxx ikp: %d  nkp: %g  prod: %g  numEig: %g' % (ikp, resObj.kpointMults[ikp], numBand * resObj.kpointMults[ikp], numEig,)
    numEig *= 2    # for two spin levels, whether numSpin is 1 or 2
    numEig = int( round( numEig))

    if self.bugLev >= 5:
      print 'calcEfermi: numSpin: %d  numKpoint: %d  numBand: %d' \
        % (numSpin, numKpoint, numBand,)
      print 'calcEfermi: numEig: %d' % (numEig,)

    avgWt = sum( resObj.kpointMults) / float( numKpoint)
    allEigs = np.zeros( [numEig])
    kk = 0
    for isp in range( numSpin):
      for ikp in range( numKpoint):
        for iband in range( numBand):
          # Replicate by kpoint weight
          for irepl in range( int( round( resObj.kpointMults[ ikp]))):
            allEigs[kk] = resObj.eigenMat[ isp, ikp, iband]
            kk += 1
            if numSpin == 1:
              # Replicate for both spins
              allEigs[kk] = allEigs[kk-1]
              kk += 1
    if kk != numEig: self.throwerr('numEig mismatch', None)

    allEigs.sort()
    if self.bugLev >= 5:
      print 'calcEfermi: numEig: %d' % (numEig,)
      print 'calcEfermi: allEigs.shape: %s' % (allEigs.shape,)

    # Find indx such that
    # occupancy = indx / sum(kpWts) == valence
    # Set dindx = num eigenvalues used.
    # The array index of the last used eigenvalue is dindx-1.
    dindx = resObj.totalValence * sum( resObj.kpointMults)
    indx = int( round( dindx)) - 1
    if indx < 0 or indx >= allEigs.shape[0]:
      self.throwerr('bad fermi.  dindx: %g  indx: %d  shape: %s' \
        % (dindx, indx, allEigs.shape), None)
    resObj.efermiCalc = allEigs[indx]

    if self.bugLev >= 5:
      print 'calcEfermi: totalValence: %g' % (resObj.totalValence,)
      print 'calcEfermi: sum( resObj.kpointMults): %g' % (sum( resObj.kpointMults),)
      print 'calcEfermi: len(allEigs): %g' % (len(allEigs),)
      print 'calcEfermi: dindx: %g  indx: %d' % (dindx, indx,)
      print 'calcEfermi: efermi:     %g' % (resObj.efermi,)
      print 'calcEfermi: efermiCalc: %g' % (resObj.efermiCalc,)
      for ii in range( max( 0, indx-10), min( numEig, indx+10)):
        msg = 'calcEfermi: allEigs[%d]: %g' % (ii, allEigs[ii],)
        if ii == indx: msg += ' ***'
        print msg

#====================================================================

  def calcBandgaps( self, resObj):

    # Conduction band min
    # cbMinMat[isp][ikp] = min of eigvals > efermi
    #
    # Valence band max
    # vbMaxMat[isp][ikp] = max of eigvals <= efermi

    numSpin = resObj.numSpin
    numKpoint = resObj.numKpoint
    numBand = resObj.numBand

    # For each isp and kpoint, what is min eigvalue > efermi
    cbMinMat = np.empty( [numSpin, numKpoint], dtype=float)
    vbMaxMat = np.empty( [numSpin, numKpoint], dtype=float)
    cbMinMat.fill( np.inf)
    vbMaxMat.fill( -np.inf)

    # For each isp, what is min or max across all kpoints
    cbMinVals = np.empty( [numSpin], dtype=float)
    vbMaxVals = np.empty( [numSpin], dtype=float)
    cbMinVals.fill( np.inf)
    vbMaxVals.fill( -np.inf)

    # For each isp, which kpoint has the min or max
    cbMinIxs = np.empty( [numSpin], dtype=int)
    vbMaxIxs = np.empty( [numSpin], dtype=int)
    cbMinIxs.fill( -1)
    vbMaxIxs.fill( -1)

    for isp in range( numSpin):
      for ikp in range( numKpoint):
        for iband in range( numBand):
          val = resObj.eigenMat[isp][ikp][iband]
          if val <= resObj.efermiCalc:
            if val > vbMaxMat[isp][ikp]: vbMaxMat[isp][ikp] = val
            if val > vbMaxVals[isp]:
              vbMaxVals[isp] = val
              vbMaxIxs[isp] = ikp

          else:    # val > resObj.efermi
            if val < cbMinMat[isp][ikp]: cbMinMat[isp][ikp] = val
            if val < cbMinVals[isp]:
              cbMinVals[isp] = val
              cbMinIxs[isp] = ikp

    # Find bandgapDirects[isp] = min gap for the same kpoint
    # Find bandgapIndirects[isp] = min gap across kpoints
    bandgapDirects = numSpin * [np.inf]
    bandgapIndirects = numSpin * [np.inf]
    for isp in range( numSpin):
      for ikp in range( numKpoint):
        gap = max( 0, cbMinMat[isp][ikp] - vbMaxMat[isp][ikp])
        if gap < bandgapDirects[isp]: bandgapDirects[isp] = gap
      bandgapIndirects[isp] = max( 0, cbMinVals[isp] - vbMaxVals[isp])

    resObj.cbMinVals = cbMinVals
    resObj.cbMinIxs  = cbMinIxs
    resObj.vbMaxVals = vbMaxVals
    resObj.vbMaxIxs  = vbMaxIxs
    resObj.bandgapDirects = bandgapDirects
    resObj.bandgapIndirects = bandgapIndirects

    # This is the PyLada version
    resObj.cbMin = min( cbMinVals)
    resObj.vbMax = max( vbMaxVals)
    resObj.bandgap = resObj.cbMin - resObj.vbMax
    if resObj.bandgap < 0: resObj.bandgap = 0

    if self.bugLev >= 5:
      print 'calcBandgaps: cbMinMat:\n%s' \
        % (self.formatMatrix( cbMinMat),)
      print 'calcBandgaps: cbMinVals: %s' % (resObj.cbMinVals,)
      print 'calcBandgaps: cbMinIxs: %s' % (resObj.cbMinIxs,)

      print 'calcBandgaps: vbMaxMat:\n%s' \
        % (self.formatMatrix( vbMaxMat),)
      print 'calcBandgaps: vbMaxVals: %s' % (resObj.vbMaxVals,)
      print 'calcBandgaps: vbMaxIxs: %s' % (resObj.vbMaxIxs,)

      print 'calcBandgaps: bandgapDirects:   %s' % (resObj.bandgapDirects,)
      print 'calcBandgaps: bandgapIndirects: %s' % (resObj.bandgapIndirects,)

      # Write plot data to tempplota%ispin
      for isp in range( numSpin):
        with open('tempplota%d' % (isp,), 'w') as fout:
          for ikp in range( numKpoint):
            print >> fout, '%g  %g' % (vbMaxMat[isp,ikp], cbMinMat[isp,ikp],)

      # Write plot data to tempplotb%ispin
      for isp in range( numSpin):
        with open('tempplotb%d' % (isp,), 'w') as fout:
          for ikp in range( numKpoint):
            for iband in range( numBand):
              print >> fout, '%d  %g' \
                % (ikp, resObj.eigenMat[isp][ikp][iband],)

#====================================================================

  # Returns a list of line numbers ixs such that at each ix,
  # lines[ix+i] matches pats[i].

  def findLines( self, pats, numMin, numMax):
    # Insure all pats are '^...$'
    regexs = []
    for pat in pats:
      regexs.append( re.compile( pat))

    resIxs = []
    for iline in range( self.numLine):
      # Do the pats match starting at iline ...
      allOk = True
      for ii in range( len( pats)):
        if iline + ii < 0 or iline + ii >= self.numLine:
          allOk = False
          break
        if not regexs[ii].match( self.lines[iline+ii]):
          allOk = False
          break
      if allOk: resIxs.append( iline)
    if len( resIxs) < numMin \
      or (numMax > 0 and len( resIxs) > numMax):
      self.throwerr(('num found mismatch.  numMin: %d  numMax: %d'
        + '  numFound: %d  pats: %s')
        % (numMin, numMax, len( resIxs), pats,), None)
    return resIxs

#====================================================================

  def parseMatrix( self, ntok, begLine, endLine, begCol, endCol):
    rows = []
    for ii in range( begLine, endLine):
      toks = self.lines[ii].split()
      if len(toks) != ntok: self.throwerr('bad ntok', ii)
      vals = map( float, toks[begCol:endCol])
      rows.append( vals)
    toks = self.lines[endLine].split()
    if len(toks) == ntok: self.throwerr('bad endLine', endLine)

    return np.array( rows, dtype=float)

#====================================================================

  def formatMatrix( self, vmat):
    if vmat == None: msg = '(Matrix is None)'
    else:
      shp = vmat.shape
      if len( shp) != 2: self.throwerr('bad shape', None)
      msg = ''
      for ii in range( shp[0]):
        msg += '  row %3d: ' % (ii,)
        for jj in range( shp[1]):
          msg += '  %7.3f' % (vmat[ii,jj],)
        msg += '\n'
    return msg

#====================================================================

  def formatMatrixPython( self, vmat):
    if vmat == None: msg = '(Matrix is None)'
    else:
      shp = vmat.shape
      if len( shp) != 2: self.throwerr('bad shape', None)
      msg = '[\n'
      for ii in range( shp[0]):
        msg += '  ['
        for jj in range( shp[1]):
          msg += ' %9.5f,' % (vmat[ii,jj],)
        msg += ' ],\n'
      msg += ']\n'
    return msg


#====================================================================

  def throwerr( self, msg, ix):
    fullMsg = '%s\n' % (msg,)
    fullMsg += '  fname: %s' % (self.fname,)
    if ix != None:
      fullMsg += '  ix: %d\n  line: %s\n' % (ix, self.lines[ix],)
    raise Exception( fullMsg)

#====================================================================


# end of class ScanOutcar


