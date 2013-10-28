#!/usr/bin/env python

import datetime, os, re, sys
import numpy as np


#====================================================================

def badparms( msg):
  print '\nError: %s' % (msg,)
  print 'Parms:'
  print '  -bugLev    <int>      debug level'
  print '  -inDir     <string>   input dir containing OUTCAR, INCAR, POSCAR'
  print ''
  sys.exit(1)

#====================================================================

def main():
  '''
  Test driver: Extracts info from a VASP OUTCAR file.

  Command line parameters:

  ================  =========    ==============================================
  Parameter         Type         Description
  ================  =========    ==============================================
  **-bugLev**       integer      Debug level.  Normally 0.
  **-inDir**       s tring       Input dir containing OUTCAR, INCAR, POSCAR
  ================  =========    ==============================================
  '''

  bugLev = 0
  inDir = None

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if key == '-bugLev': bugLev = int( val)
    elif key == '-inDir': inDir = val
    else: badparms('unknown key: "%s"' % (key,))

  if bugLev == None: badparms('parm not specified: -bugLev')
  if inDir == None: badparms('parm not specified: -inDir')

  resObj = ResClass()
  scanner = ScanOutcar( bugLev, inDir, resObj)


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
      self.throwerr('invalid spec: %s' % (self,))
    if which not in ['first', 'last']:
      self.throwerr('invalid spec: %s' % (self,))
    if tp not in [ int, float, str]:
      self.throwerr('invalid spec: %s' % (self,))

    self.regex = re.compile( pat)

  def __str__( self):
    res = 'tag: %s  pat: %s  which: %s  numMin: %d  numMax: %d  tp: %s' \
      % (self.tag, repr( self.pat), self.which,
        self.numMin, self.numMax, self.tp,)
    return res

  def throwerr( self, msg):
    raise Exception( msg)

#====================================================================
#====================================================================


# Fills resObj.

class ScanOutcar:

  def __init__( self, bugLev, inDir, resObj):
    self.bugLev = bugLev
    self.inDir = inDir

    # First, read POSCAR and INCAR
    self.parseIncar( resObj)
    self.parsePoscar( resObj)

    # Now read OUTCAR
    fname = os.path.join( inDir, 'OUTCAR')
    with open( fname) as fin:
      self.lines = fin.readlines()
    self.numLine = len( self.lines)
    # Strip all lines
    for ii in range( self.numLine):
      self.lines[ii] = self.lines[ii].strip()

    self.getScalars( resObj)
    self.getDate( resObj)
    self.getTimes( resObj)
    self.getSystem( resObj)
    self.getCategEnergy( resObj)
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


#====================================================================

  def parseIncar( self, resObj):
    fname = os.path.join( self.inDir, 'INCAR')
    with open( fname) as fin:
      lines = fin.readlines()

    for iline in range( len( lines)):
      line = lines[iline].strip()
      if len(line) > 0 and not line.startswith('#'):
        mat = re.match('^([a-zA-Z0-9]+) *= *(.*)$', line)
        if mat == None:
          self.throwerr('invalid line.  iline: %d  line: %s' % (iline, line,),
            None)
        key = mat.group(1)
        val = mat.group(2)

        ix = val.find('#')           # get rid of trailing comment
        if ix >= 0: val = val[:ix].strip()

        val = val.strip('"\'')       # strip possibly unbalanced quotes
        resObj.__dict__[key] = val
        if self.bugLev >= 5:
          print 'parseIncar: %s: %s' % (key, val,)

    if not resObj.__dict__.has_key('ALGO'):
      resObj.__dict__['ALGO'] = 'Normal'
    algo = resObj.ALGO.lower()
    if algo == 'a': algo = 'all'

    if algo in ['chi', 'gw', 'gw0', 'scgw', 'scgw0', 'diag']:
      resObj.isGw = True
    elif algo in [ 'all', 'conjugate', 'damped',
      'eigenval', 'fast', 'none', 'normal',
      'nothing', 'subrot', 'veryfast']:
      resObj.isGw = False
    else: self.throwerr('unknown algo: %s' % (algo,), None)


#====================================================================


  def parsePoscar( self, resObj):
    fname = os.path.join( self.inDir, 'POSCAR')
    with open( fname) as fin:
      lines = fin.readlines()
    for ii in range( len( lines)):
      lines[ii] = lines[ii].strip()

    iline = 0
    sysName = lines[iline].strip('"\'')   # strip possibly unbalanced quotes
    iline += 1

    posScaleFactor = float( lines[iline])
    iline += 1

    basisList = []
    for ii in range(3):
      line = lines[iline]
      iline += 1
      toks = line.split()
      if len(toks) != 3:
        self.throwerr('invalid basis.  iline: %d  line: %s' % (iline, line,),
          None)
      basisList.append( map( float, toks))
    basisMat = posScaleFactor * np.array( basisList, dtype=float)

    # typeNames
    # This is not documented at
    # http://cms.mpi.univie.ac.at/vasp/vasp/POSCAR_file.html
    # Some POSCAR files have an inserted line with the typeNames.
    line = lines[iline]
    if re.match('^\d+ .*$', line):   # if no typeNames, we hit typeNums
      typeNames = None
    else:                            # else get typeNames
      iline += 1
      typeNames = line.split()

    # typeNums
    line = lines[iline]
    iline += 1
    toks = line.split()
    typeNums = map( int, toks)

    # posType: 'direct' or 'cartesian'
    posType = lines[iline].lower()
    iline += 1

    # fracPosMat, cartPosMat
    posList = []
    for ii in range( sum( typeNums)):
      line = lines[iline]
      iline += 1
      toks = line.split()
      if len(toks) != 3:
        self.throwerr('invalid pos.  iline: %d  line: %s' % (iline, line,),
          None)
      posList.append( map( float, toks))
    posMat = np.array( posList, dtype=float)

    if posType in ['d', 'direct']:
      fracPosMat = posMat
      cartPosMat = np.dot( fracPosMat, basisMat)
    elif posType in ['c', 'cartesian']:
      cartPosMat = posMat * scaleFactor
      fracPosMat = np.dot( cartPosMat, np.linalg.inv( basisMat))
    else: self.throwerr('unknown posType: %s' % (posType,), None)

    resObj.posScaleFactor = posScaleFactor
    resObj.typeNames = typeNames
    resObj.typeNums = typeNums
    # Ignore the matrix items in POSCAR, as they sometimes
    # differ from OUTCAR and the word is that OUTCAR is correct.
    # resObj.initialBasisMat = basisMat
    # resObj.initialFracPosMat = directMat
    # resObj.initialCartPosMat = cartMat
    if self.bugLev >= 5:
      print 'parsePoscar: posScaleFactor: %s' % (resObj.posScaleFactor,)
      print 'parsePoscar: typeNames: %s' % (typeNames,)
      print 'parsePoscar: typeNums: %s' % (typeNums,)
      print 'parsePoscar: unused initialBasisMat: %s' % (basisMat,)
      print 'parsePoscar: unused initialFracPosMat: %s' % (fracPosMat,)
      print 'parsePoscar: unused initialCartPosMat: %s' % (cartPosMat,)



#====================================================================

  def getScalars( self, resObj):
    #   k-points           NKPTS =    260   k-points in BZ     NKDIM =    260   number of bands    NBANDS=     11
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
      # ALGO = Fast
      # ALGO    =GW        execute GW part
      Sspec( 'algo', r'^ALGO *= *([a-zA-Z0-9]+).*$',
        'first', 0, 1, str),
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

      # Volume
      #   volume of cell :       20.0121
      Sspec( 'finalVolume_ang3', r'^volume of cell *: +([-.E0-9]+)$',
        'last', 1, 0, float),

    ] # specs

    for spec in specs:
      ixs = self.findLines( [spec.pat], spec.numMin, spec.numMax)
      if len(ixs) > 0:
        if spec.which == 'first': ix = ixs[0]
        elif spec.which == 'last': ix = ixs[-1]
        else: self.throwerr('invalid which in spec: %s' % (spec,), None)
        mat = spec.regex.match( self.lines[ix])
        value = spec.tp( mat.group(1))

        if resObj.__dict__.has_key( spec.tag):
          if resObj.__dict__[spec.tag] != value:
            self.throwerr('value conflict: spec: %s  INCAR: %s  OUTCAR: %s' \
              % (spec, resObj.__dict__[spec.tag], value,), None)
        else:
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

  # iterCpuTimes    (not in GW calcs)
  # iterRealTimes   (not in GW calcs)
  # Lines are like either of:
  #   LOOP+:  cpu time   22.49: real time   24.43
  #   LOOP+:  VPU time   42.93: CPU time   43.04
  #   LOOP+:  cpu time16935.65: real time16944.21
  #   LOOP+:  cpu time********: real time********

  # In the second line, "VPU" means CPU, and "CPU" means wall time.
  # See: http://cms.mpi.univie.ac.at/vasp-forum/forum_viewtopic.php?3.336
  #
  # In all calcs get:
  #                 Total CPU time used (sec):       11.725
  #                         User time (sec):        9.392
  #                       System time (sec):        2.334
  #                      Elapsed time (sec):       14.468

  def getTimes( self, resObj):
    pat = r'^LOOP\+ *: +[a-zA-Z]+ +time *([.0-9]+): +[a-zA-Z]+' \
      + r' +time *([.0-9]+)$'
    if resObj.isGw:
      resObj.iterCpuTimes = None
      resObj.iterRealTimes = None
    else:
      # numMin should be 1, but fortran prints *** for big nums.
      ixs = self.findLines( [pat], 0, 0)        # pats, numMin, numMax
      if len(ixs) == 0:
        resObj.iterCpuTimes = None
        resObj.iterRealTimes = None
      else:
        cpuTimes = []
        realTimes = []
        for ix in ixs:
          mat = re.match( pat, self.lines[ix])
          cpuTimes.append( float( mat.group(1)))
          realTimes.append( float( mat.group(2)))
        resObj.iterCpuTimes = cpuTimes
        resObj.iterRealTimes = realTimes

    pat = r'^Total CPU time used \(sec\): +([.0-9]+)$'
    ixs = self.findLines( [pat], 1, 1)        # pats, numMin, numMax
    mat = re.match( pat, self.lines[ixs[0]])
    resObj.totalCpuTimeSec = mat.group(0)

    pat = r'^User time \(sec\): +([.0-9]+)$'
    ixs = self.findLines( [pat], 1, 1)        # pats, numMin, numMax
    mat = re.match( pat, self.lines[ixs[0]])
    resObj.userTimeSec = mat.group(0)

    pat = r'^System time \(sec\): +([.0-9]+)$'
    ixs = self.findLines( [pat], 1, 1)        # pats, numMin, numMax
    mat = re.match( pat, self.lines[ixs[0]])
    resObj.systemTimeSec = mat.group(0)

    pat = r'^Elapsed time \(sec\): +([.0-9]+)$'
    ixs = self.findLines( [pat], 1, 1)        # pats, numMin, numMax
    mat = re.match( pat, self.lines[ixs[0]])
    resObj.elapsedTimeSec = mat.group(0)

    if self.bugLev >= 5:
      print 'getTimes: iterCpuTimes: %s' % (resObj.iterCpuTimes,)
      print 'getTimes: iterRealTimes: %s' % (resObj.iterRealTimes,)
      print 'getTimes: totalCpuTimeSec: %s' % (resObj.totalCpuTimeSec,)
      print 'getTimes: userTimeSec: %s' % (resObj.userTimeSec,)
      print 'getTimes: systemTimeSec: %s' % (resObj.systemTimeSec,)
      print 'getTimes: elapsedTimeSec: %s' % (resObj.elapsedTimeSec,)

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

  # For doc on ALGO see:
  # http://cms.mpi.univie.ac.at/vasp/vasp/Recipe_selfconsistent_GW_calculations.html
  # http://cms.mpi.univie.ac.at/vasp/vasp/Recipe_GW_calculations.html
  # http://cms.mpi.univie.ac.at/wiki/index.php/ALGO

  def getCategEnergy( self, resObj):

    if resObj.isGw:
      resObj.energyNoEntrp = None
      resObj.efermi = None

    else:
      # Spacing varies:
      # energy without entropy =  -60.501550  energy(sigma->0) =  -60.501640
      # energy  without entropy=  -15.051005  energy(sigma->0) =  -15.051046

      pat = r'^energy +without +entropy *= *([-.E0-9]+)' \
        + r' +energy\(sigma->0\) *= *[-.E0-9]+$'
      ixs = self.findLines( [pat], 1, 0)        # pats, numMin, numMax
      ix = ixs[-1]
      mat = re.match( pat, self.lines[ix])
      resObj.energyNoEntrp = float( mat.group(1))

      #   E-fermi :   6.5043     XC(G=0): -12.1737     alpha+bet :-11.7851
      pat = r'^E-fermi *: *([-.E0-9]+) +XC.*alpha\+bet.*$'
      ixs = self.findLines( [pat], 1, 0)        # pats, numMin, numMax
      ix = ixs[-1]
      mat = re.match( pat, self.lines[ix])
      resObj.efermi = float( mat.group(1))

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

    if resObj.typeNames == None:   # if POSCAR didn't have typeNames
      resObj.typeNames = typeNames
    else:
      if typeNames != resObj.typeNames:
        self.throwerr('typeNames mismatch.  POSCAR: %s  OUTCAR: %s' \
          % (resObj.typeNames, typeNames,), None)

    if self.bugLev >= 5:
      print 'getTypeNames: typeNames: %s' % (resObj.typeNames,)

#====================================================================

  # typeNums == stoichiometry
  #   ions per type =               1   1
  def getTypeNums( self, resObj):
    pat = r'^ions per type *= '
    ixs = self.findLines( [pat], 1, 1)        # pats, numMin, numMax
    toks = self.lines[ixs[0]].split()
    typeNums = map( int, toks[4:])
    if typeNums != resObj.typeNums:
      self.throwerr('typeNums mismatch.  POSCAR: %s  OUTCAR: %s' \
        % (resObj.typeNums, typeNums,), None)
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
    initialBasisMat = self.parseMatrix(
      6, ix+1, ix+4, 0, 3)       # ntok, rowBeg, rowEnd, colBeg, colEnd
    initialRecipBasisMat = self.parseMatrix(
      6, ix+1, ix+4, 3, 6)       # ntok, rowBeg, rowEnd, colBeg, colEnd

    # The basisMats can differ from POSCAR by 1.e-1 or so.  Why?
    # Use the OUTCAR version.
    resObj.initialBasisMat = initialBasisMat
    resObj.initialRecipBasisMat = initialRecipBasisMat

    ix = ixs[-1]  # final
    # In vasprun.xml and OUTCAR, the basis vectors are rows.
    # In PyLada, Mayeul uses the transpose.
    resObj.finalBasisMat = self.parseMatrix(
      6, ix+1, ix+4, 0, 3)       # ntok, rowBeg, rowEnd, colBeg, colEnd
    resObj.finalRecipBasisMat = self.parseMatrix(
      6, ix+1, ix+4, 3, 6)       # ntok, rowBeg, rowEnd, colBeg, colEnd

    # Test the linear algebra
    test_initialRecip = np.linalg.inv( resObj.initialBasisMat).T
    test_finalRecip = np.linalg.inv( resObj.finalBasisMat).T

    if self.bugLev >= 5:
      print 'getBasisMats: initialBasisMat:\n%s' \
        % (repr( resObj.initialBasisMat),)
      print 'getBasisMats: initialRecipBasisMat:\n%s' \
        % (repr( resObj.initialRecipBasisMat),)
      print 'getBasisMats: test_initialRecip:\n%s' \
        % (repr( test_initialRecip),)

      print 'getBasisMats: finalBasisMat:\n%s' \
        % (repr( resObj.finalBasisMat),)
      print 'getBasisMats: finalRecipBasisMat:\n%s' \
        % (repr( resObj.finalRecipBasisMat),)
      print 'getBasisMats: test_finalRecip:\n%s' \
        % (repr( test_finalRecip),)

    # Test the linear algebra
    self.checkClose( resObj.initialRecipBasisMat, test_initialRecip, 1.e-3)
    self.checkClose( resObj.finalRecipBasisMat, test_finalRecip, 1.e-3)

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
    initialFracPosMat = self.parseMatrix(
      3, ix+1, ix+1+resObj.numAtom, 0, 3)
      # ntok, rowBeg, rowEnd, colBeg, colEnd
    # The posMats can differ by 1.e-1 or so.  Why?
    # Use the OUTCAR version.
    resObj.initialFracPosMat = initialFracPosMat

    ixs = self.findLines( [patc], 1, 1)  # pats, numMin, numMax
    ix = ixs[0]
    initialCartPosMat = self.parseMatrix(
      3, ix+1, ix+1+resObj.numAtom, 0, 3)
      # ntok, rowBeg, rowEnd, colBeg, colEnd
    # The posMats can differ by 1.e-1 or so.  Why?
    # Use the OUTCAR version.
    resObj.initialCartPosMat = initialCartPosMat

    # Test the linear algebra
    test_initialFracPosMat = np.dot(
      initialCartPosMat, np.linalg.inv( resObj.initialBasisMat))
    test_initialCartPosMat = np.dot(
      initialFracPosMat, resObj.initialBasisMat)
    self.checkClose( initialFracPosMat, test_initialFracPosMat, 1.e-3)
    self.checkClose( initialCartPosMat, test_initialCartPosMat, 1.e-3)

    if self.bugLev >= 5:
      print 'getInitialPositions: initialFracPosMat:\n%s' \
        % (self.formatMatrix( initialFracPosMat),)
      print 'getInitialPositions: initialCartPosMat:\n%s' \
        % (self.formatMatrix( initialCartPosMat),)


#====================================================================

  # finalCartPosMat, forceMat
  #   POSITION                       TOTAL-FORCE (eV/Angst)
  #   ------------------------------------------------------------------
  #   0.59671  5.05062  2.21963       0.003680   -0.001241  -0.004039
  #   4.98024  2.21990  0.58287       -0.000814  -0.015091  -0.012495
  #   2.23430  0.66221  5.03287       0.017324   0.003318   -0.014394
  #   ...
  #   ------------------------------------------------------------------
  #
  # Not found in gw calcs.

  def getFinalPositionsForce( self, resObj):
    pat = r'^POSITION +TOTAL-FORCE \(eV/Angst\)$'
    if resObj.isGw:
      resObj.finalFracPosMat = None
      resObj.finalCartPosMat = None
      resObj.finalForceMat_ev_ang = None
    else:
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
  #
  # Not in gw calcs.

  def getStressMat( self, resObj):
    pat = r'^FORCE on cell *= *-STRESS in cart. coord. +units \(eV\) *:$'
    if resObj.isGw:
      resObj.finalStressMat_ev = None
      resObj.finalStressMat_kbar = None
      resObj.finalPressure_kbar = None
    else:
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

    ixs = self.findLines(
      [headPat, blankPat, recipPat, wtPat], 1, 0)   # pats, numMin, numMax

    # Get kpointFracMat == generated reciprocol fractional coords.
    # This is what vasprun.xml calls "kpoints".
    # If there are multiple occurances use the first.
    ix = ixs[0] + 4               # start of matrix
    kpMat = self.parseMatrix(     # kpoints and weights (multiplicities)
      4, ix, ix+numKpoint, 0, 4)  # ntok, rowBeg, rowEnd, colBeg, colEnd
    resObj.kpointFracMat = kpMat[ :, 0:3]

    kpMults = kpMat[ :, 3]
    resObj.kpointMults = kpMults
    resObj.kpointWeights = kpMults / float( kpMults.sum())
    if self.bugLev >= 5:
      print 'getKpointMat: gen frac: kpointMults: %s' \
        % (resObj.kpointMults,)
      print 'getKpointMat: gen frac: kpointWeights: %s' \
        % (resObj.kpointWeights,)
      print 'getKpointMat: gen frac: kpointFracMat:\n%s' \
        % (resObj.kpointFracMat,)

    # Get generated cartesian coords
    ixCart = ix + numKpoint + 1
    ixs = self.findLines( [cartPat, wtPat], 1, 0)   # pats, numMin, numMax
    if ixs[0] != ixCart: self.throwerr('kpoint format', ixCart)
    ix = ixCart + 2              # start of matrix
    kpMat = self.parseMatrix(    # kpoints and weights (multiplicities)
      4, ix, ix+numKpoint, 0, 4) # ntok, rowBeg, rowEnd, colBeg, colEnd
    resObj.kpointCartMat = kpMat[ :, 0:3]
    test_kpointMults = kpMat[ :, 3]
    self.checkClose( resObj.kpointMults, test_kpointMults, 1.e-3)
    if self.bugLev >= 5:
      print 'getKpointMat: gen frac: test_kpointMults: %s' \
        % (test_kpointMults,)
      print 'getKpointMat: gen cart: kpointCartMat:\n%s' \
        % (resObj.kpointCartMat,)
      print 'xxxxxx kpointCartMat = %s' % (repr(resObj.kpointCartMat),)
      print 'xxxxxx test_kpointMults = %s' % (repr(test_kpointMults),)

    # Test the linear algebra
    test_kpointCartMat = resObj.posScaleFactor * np.dot(
      resObj.kpointFracMat, resObj.initialRecipBasisMat)
    if self.bugLev >= 5:
      print 'getKpointMat: gen test_kpointCartMat:\n%s' \
        % (test_kpointCartMat,)
      print 'xxxxxx test_kpointCartMat = %s' % (repr(test_kpointCartMat),)
    # This can vary by nearly 0.01, for example
    # in /projects/ppmdd/pub_data/2013_PRB_GGAUvsHSE/HSE+GW/Zn1O1_gw
    self.checkClose( resObj.kpointCartMat, test_kpointCartMat, 1.e-1)

    # Get the actual kpoints
    #
    #     k-points in units of 2pi/SCALE and weight:
    #  or k-points in units of 2pi/SCALE and weight: Automatic generation
    #     0.00000000  0.00000000  0.00000000       0.016
    #     0.08286762 -0.04784364  0.00000000       0.094
    #     ...
    #     0.16573524  0.00000000  0.15507665       0.094
    #
    #     k-points in reciprocal lattice and weights:
    #  or k-points in reciprocal lattice and weights: Automatic generation
    #     0.00000000  0.00000000  0.00000000       0.016
    #     0.25000000  0.00000000  0.00000000       0.094
    #     ...

    pat = r'^k-points in units of 2pi/SCALE and weight:' \
      + '( Automatic generation)?$'
    ixs = self.findLines( [pat], 1, 1)    # pats, numMin, numMax
    ix = ixs[0] + 1
    kpMat = self.parseMatrix(     # kpoints and weights (multiplicities)
      4, ix, ix+numKpoint, 0, 4)  # ntok, rowBeg, rowEnd, colBeg, colEnd
    actual_kpointCartMat_a = kpMat[ :, 0:3]
    wts = kpMat[ :, 3]
    # Sometimes the wts are not normalized to 1, for example in
    #   icsd_633029.cif/non-magnetic/relax_cellshape/1
    # the sum is 1.024
    actual_kpointWeights_a = wts / sum( wts)
    actual_kpointFracMat_a = (1. / resObj.posScaleFactor) * np.dot(
      actual_kpointCartMat_a, np.linalg.inv( resObj.initialRecipBasisMat))
    if self.bugLev >= 5:
      print 'getKpointMat: actual_kpointWeights_a: %s' \
        % (actual_kpointWeights_a,)
      print 'getKpointMat: actual_kpointCartMat_a:\n%s' \
        % (actual_kpointCartMat_a,)
      print 'getKpointMat: actual_kpointFracMat_a:\n%s' \
        % (actual_kpointFracMat_a,)

    pat = r'^k-points in reciprocal lattice and weights:' \
      + '( Automatic generation)?$'
    ixs = self.findLines( [pat], 1, 1)    # pats, numMin, numMax
    ix = ixs[0] + 1
    kpMat = self.parseMatrix(     # kpoints and weights (multiplicities)
      4, ix, ix+numKpoint, 0, 4)  # ntok, rowBeg, rowEnd, colBeg, colEnd
    actual_kpointFracMat_b = kpMat[ :, 0:3]
    wts = kpMat[ :, 3]
    # Sometimes the wts are not normalized to 1, for example in
    #   icsd_633029.cif/non-magnetic/relax_cellshape/1
    # the sum is 1.024
    actual_kpointWeights_b = wts / sum( wts)
    actual_kpointCartMat_b = resObj.posScaleFactor * np.dot(
      actual_kpointFracMat_b, resObj.initialRecipBasisMat)
    if self.bugLev >= 5:
      print 'getKpointMat: actual_kpointWeights_b: %s' \
        % (actual_kpointWeights_b,)
      print 'getKpointMat: actual_kpointCartMat_b:\n%s' \
        % (actual_kpointCartMat_b,)
      print 'getKpointMat: actual_kpointFracMat_b:\n%s' \
        % (actual_kpointFracMat_b,)

    # This doesn't work.  Some sets of weights don't work this way.
    # For example, lany.projects.ppmdd.pub_data.2013_PRB_GGAUvsHSE/
    # GGAU_defects/Al1N1/Vc_Al/OUTCAR gives 
    # uniqWts: [0.015952143569292122, 0.030907278165503486,
    #   0.046859421734795605, 0.093718843469591209, 0.18743768693918242]
    # fac = 1/uniqWts[0] = 62.6875
    # uniqWts * fac are not integers
    #
    ## Find kpoint multiplicities by multiplying kpointWeights
    ## by the min value that makes them all integers
    #wts = actual_kpointWeights_a
    #uniqWts = list( set( wts))
    #uniqWts.sort()
    #minWt = uniqWts[0]
    #if self.bugLev >= 5:
    #  print 'getKpointMat: wts: %s' % (wts,)
    #  print 'getKpointMat: uniqWts: %s' % (uniqWts,)
    #  print 'getKpointMat: minWt: %s' % (minWt,)
    #factor = None
    #for ii in range(1, 10):
    #  tfact = ii / float( minWt)
    #  allOk = True
    #  for wt in uniqWts:
    #    val = tfact * wt
    #    if abs( val - round(val)) > 1.e-5:
    #      allOk = False
    #      break
    #  if allOk:
    #    factor = tfact
    #    break
    #if factor == None: self.throwerr('no kpointMults found', None)
    #actual_kpointMults_a = wts * factor
    #self.checkClose( resObj.kpointMults, actual_kpointMults_a, 1.e-3)

    # Check that generated points == actuals.
    if not hasattr( resObj, 'kpointFracMat'):
      self.throwerr('no generated kpoints found', None)
    self.checkClose( resObj.kpointWeights, actual_kpointWeights_a, 1.e-3)
    self.checkClose( resObj.kpointFracMat, actual_kpointFracMat_a, 1.e-2)
    self.checkClose( resObj.kpointCartMat, actual_kpointCartMat_a, 1.e-3)

    self.checkClose( resObj.kpointWeights, actual_kpointWeights_b, 1.e-3)
    self.checkClose( resObj.kpointFracMat, actual_kpointFracMat_b, 1.e-3)
    self.checkClose( resObj.kpointCartMat, actual_kpointCartMat_b, 1.e-2)

    if self.bugLev >= 5:
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

    if len(compIxs) == 0:         # if no spin components, or gw calc ...
      if numSpin != 1: self.throwerr('numSpin mismatch', None)
    else:                         # else we have spin components ...
      if numSpin != 2: self.throwerr('numSpin mismatch', None)

    # Not found in gw calc
    if resObj.isGw:
      resObj.eigenMat = None
      resObj.occupMat = None
      if self.bugLev >= 5:
        print 'getEigenMat: eigenMat: None  occupMat: None'
    else:
      firstIxs = self.findLines( [kpFirstPat, bandPat], 1, 0)
      for isp in range( numSpin):
        istart = firstIxs[ -numSpin + isp]    # use the last
        for ikp in range( numKpoint):
          # Parse one k-point section, for numBand lines
          isection = istart + 2 + ikp * (3 + numBand)
          tmat = self.parseMatrix(
            3, isection, isection + numBand, 1, 3)  # ntok,rBeg,rEnd,cBeg,cEnd
          eigenMat[ isp, ikp, 0:numBand] = tmat[ 0:numBand, 0]  # col 0: eigen
          occupMat[ isp, ikp, 0:numBand] = tmat[ 0:numBand, 1]  # col 1: occup

      resObj.eigenMat = eigenMat
      resObj.occupMat = occupMat

      if self.bugLev >= 5:
        for isp in range( resObj.numSpin):
          print 'getEigenMat: isp: %d  eigenMat:\n%s' \
            % (isp, resObj.eigenMat[isp],)
        for isp in range( resObj.numSpin):
          print 'getEigenMat: isp: %d  occupMat:\n%s' \
            % (isp, resObj.occupMat[isp],)

#====================================================================


  def calcMisc( self, resObj):

    if resObj.iterRealTimes == None: resObj.iterTotalTime = None
    else: resObj.iterTotalTime = sum( resObj.iterRealTimes)
    if self.bugLev >= 5:
      print 'calcMisc: iterTotalTime: %s' % (resObj.iterTotalTime,)


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
    if resObj.isGw:
      resObj.efermiCalc = None

    else:

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

    if resObj.isGw:
      resObj.cbMinVals = None
      resObj.cbMinIxs  = None
      resObj.vbMaxVals = None
      resObj.vbMaxIxs  = None
      resObj.bandgapDirects = None
      resObj.bandgapIndirects = None

    else:
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

        print '\ncalcBandgaps: efermiCalc: %g' % (resObj.efermiCalc,)
        for isp in range( numSpin):
          print '\ncalcBandgaps: start isp: %d' % (isp,)
          for ikp in range( numKpoint):
            vval = vbMaxMat[isp][ikp]
            cval = cbMinMat[isp][ikp]
            vmsg = '%8.4f' % (vval,)
            cmsg = '%8.4f' % (cval,)
            if ikp == vbMaxIxs[isp]: vmsg += ' ***'
            if ikp == cbMinIxs[isp]: cmsg += ' ***'
            print '  isp: %d  ikp: %3d  vbMaxMat: %-14s  cbMinMat: %-14s' \
              % ( isp, ikp, vmsg, cmsg,)
          print ''

        print 'calcBandgaps: vbMaxIxs: %s' % (resObj.vbMaxIxs,)
        print 'calcBandgaps: vbMaxVals: %s' % (resObj.vbMaxVals,)
        print 'calcBandgaps: cbMinIxs: %s' % (resObj.cbMinIxs,)
        print 'calcBandgaps: cbMinVals: %s' % (resObj.cbMinVals,)

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

  def checkClose( self, mata, matb, absErr):
    if mata == None or matb == None:
      self.throwerr('mata or matb is None', None)
    if mata.shape != matb.shape:
      self.throwerr('checkClose: shape mismatch: mata: %s  matb: %s' \
        % (mata.shape, matb.shape,))
    if np.max( np.abs( mata - matb)) > absErr:
      msg = 'checkClose: mismatch.\n'
      msg += 'mata:\n%s\n' % (mata,)
      msg += 'matb:\n%s\n' % (matb,)
      msg += 'delta = matb - mata:\n%s\n' % (matb - mata,)
      msg += 'max abs delta: %g\n' % (np.max( np.abs( matb - mata)))
      msg += '\ncheckClose: mismatch.  See above.'
      self.throwerr( msg, None)


#====================================================================

  def throwerr( self, msg, ix):
    fullMsg = '%s\n' % (msg,)
    fullMsg += '  inDir: %s' % (self.inDir,)
    if ix != None:
      fullMsg += '  ix: %d\n  line: %s\n' % (ix, self.lines[ix],)
    raise Exception( fullMsg)

#====================================================================

# end of class ScanOutcar

#====================================================================

if __name__ == '__main__': main()

