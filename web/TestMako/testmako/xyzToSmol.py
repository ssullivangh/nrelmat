#!/usr/bin/env python

import copy, json, math, re, sys
import numpy as np

# Reads an xyz format file, determines likely bonds,
# and writes an smol file.
#
#
#
#
# XYZ format:
#
#   numberOfAtoms
#   description
#   sym x y z
#   sym x y z
#   ...
#
# Example xyz file format:
#   3
#   Carbon dioxide
#   O -1  0  0
#   C  0  0  0
#   O  1  0  0
#
#
#
#
#
#
# xxx redo: now is JSON
# Smol format:
# 
# Blank lines and comments, which start with '#' after
# initial whitespace, are ignored.
# 
# The first word of non-comment lines determines the line type.
# The line types are:
#
#   Line type    Parameters        Meaning
#   -----------  ----------------  ------------------------------------------
#
#   description  words             Description of the file or the study
#
#   element      sym radius color  Specifies element characteristics:
#                                  atomicRadius in pm, color as 6 hex digits.
#
#   coordType    tp                cartesian or direct: specifies the type
#                                  of coords in the atom lines.
#                                  If coordType=='cartesian',
#                                  both posScale and basisMatrix are omitted.
#
#   posScale     sval              position scale factor
#
#   basisMatrix  va vb vc          Basis matrix, such that
#                                  cartesianPosMatInAngstrom
#                                    = posScale * directPosMat * basisMat
#
#   atom         sym x y z         Specifies an atom position.
#                                  If coordType is "direct", this is
#                                  the directPosMat.
#                                  If "cartesian", this is the cartesianPosMat.
#
#   bond         ixa ixb           Specifies a bond between two atoms,
#                                  using the indices of the atoms, origin 0.
# 
# The sections must occur in order:
# description before element lines before basis lines, etc.
#
# Example smol file:
#   description Carbon dioxide
# 
#   element       C 70 909090
#   element       O 60 ff0d0d
#
#   coordType     direct
#   posScale      1.0
#   basisMatrix   1    0    0
#   basisMatrix   0    1    0
#   basisMatrix   0    0    1
# 
#   atom          O -1  0  0
#   atom          C  0  0  0
#   atom          O  1  0  0
# 
#   bond          0  1
#   bond          1  2





class Atom:

  def __init__(self, aix, asym, directCoords, elementMap):
    self.aix = aix
    self.asym = asym
    self.directCoords = directCoords
    self.elementMap = elementMap
    self.acluster = None
    self.origAtom = self       # Reflected atoms point to the original,
                               # Used for bond counting.
    self.numBond = 0           # Num bonds.  Used for origAtoms only.

    self.bonds = []            # list of bond atoms
    if not self.elementMap.has_key(asym):
      throwerr('Atom: invalid symbol: "%s"' % (asym,))
    gp = self.elementMap[asym].egroup

    # He, Ne, Ar, Kr, Xe, ...
    if gp == 18: self.maxBond = 0
    # H, Li, Na, K, ... and F, Cl, Br, I, ...
    elif gp == 1 or gp == 17: self.maxBond = 1
    # Be, Mg, Ca, Sr, ... and O, S, Se, Te, ...
    elif gp == 2 or gp == 16: self.maxBond = 2
    # Sc, Y, La, Ac, ... or N, P, As, Sb, ...
    elif gp == 3 or gp == 15: self.maxBond = 3
    else: self.maxBond = float('inf')

    self.maxBond = float('inf')          # xxx allow any num bonds

  def __str__(self):
    res = '%s%d' % (self.asym, self.aix,)
    return res

  def format(self):
    res = 'aix: %d  asym: %s  directCoords: %s' \
      % (self.aix, self.asym, self.directCoords,)
    res += '  bonds: '
    for atomb in self.bonds:
      res += ' %s%d' % (atomb.asym, atomb.aid,)
    if self.acluster != None: res += '  acluster: %d' % (self.acluster.cid,)
    return res

  def addBond( self, atom):
    self.bonds.append( atom)
    self.origAtom.numBond += 1
    if self.origAtom.numBond > self.origAtom.maxBond:
      throwerr('too many bonds: atom: %s' % (self.format(),))



class Cluster:

  idCounter = 0
  def __init__(self):
    self.cid = Cluster.idCounter
    Cluster.idCounter += 1
    self.atoms = []
    self.kida = None
    self.kidb = None
    self.distance = None

  def addAtom( self, atom):
    self.atoms.append( atom)
    atom.acluster = self

  def merge(self, cluster, distance):
    newClus = Cluster()
    newClus.atoms = self.atoms + cluster.atoms
    for atom in newClus.atoms:
      atom.acluster = newClus
    newClus.kida = self
    newClus.kidb = cluster
    newClus.distance = distance
    return newClus

  def __str__(self):
    atomStgs = [str(atom) for atom in self.atoms]
    atomMsg = ' '.join( atomStgs)
    if self.distance == None:
      if self.kida != None or self.kidb != None:
        throwerr('invalid kids')
      res = 'cid: %d  atoms: %s' % (self.cid, atomMsg,)
    else:
      res = 'cid: %d  kids: %d  %d  dist: %.4f  atoms: %s' \
        % (self.cid, self.kida.cid, self.kidb.cid, self.distance, atomMsg,)
    return res




class Bond:
  def __init__( self, atoma, atomb, distance, ca, cb, cc):
    self.atoma = atoma
    self.atomb = atomb
    self.distance = distance
    self.clustera = ca          # old A
    self.clusterb = cb          # old B
    self.clusterc = cc          # new merged
    atoma.addBond( atomb)
    atomb.addBond( atoma)

  def __str__(self):
    eleMap = self.atoma.elementMap
    res = '%-5s  %-5s  dist: %.4f  rada: %.3f  radb: %.3f  ca: %3d  cb: %3d  cc: %3d' \
      % (self.atoma, self.atomb, self.distance,
        0.01 * eleMap[self.atoma.asym].eradiusAtomic_pm,  # pm to Angstrom
        0.01 * eleMap[self.atomb.asym].eradiusAtomic_pm,  # pm to Angstrom
        self.clustera.cid, self.clusterb.cid, self.clusterc.cid,)
    return res





def badparms(msg):
  print 'Error: ', msg
  print 'Parms:'
  print ''
  print '  -bugLev    Debug level'
  print ''
  print '  -distType  Center or shell: distance from centers or atom shells'
  print ''
  print '  -posScale  Scale factor for input dists, such that'
  print '             cartesianPosMatInAngstrom'
  print '             = posScale * directPosMat * basisMat'
  print ''
  print '  -inFile    Name of input xyz format file'
  print ''
  print '  -outFile   Name of output smol format file'
  print ''
  print 'See pgm doc for info on xyz and smol formats.'
  print ''
  print 'Example:'
  print './xyzToSmol.py -distType shell -posScale 1 -inFile tempa -outFile tempb'

  sys.exit(1)










def main():
  bugLev = None
  distType = None
  posScale = None
  inFile = None
  outFile = None
  if len(sys.argv) % 2 != 1: badparms("parms must be key/value pairs")
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if   key == '-bugLev': bugLev = int( val)
    elif key == '-distType': distType = val
    elif key == '-posScale': posScale = float( val)
    elif key == '-inFile': inFile = val
    elif key == '-outFile': outFile = val
    else: badparms('unknown key: "' + key + '"')

  if bugLev == None: badparms('parm not specified: -bugLev')
  if distType == None: badparms('parm not specified: -distType')
  if posScale == None: badparms('parm not specified: -posScale')
  if inFile == None: badparms('parm not specified: -inFile')
  if outFile == None: badparms('parm not specified: -outFile')

  basisMat = np.array( [
    [  1,  0,  0],
    [  0,  1,  0],
    [  0,  0,  1]
  ])

  elementMap = getElementMap()

  (description, atoms) = readXyz( inFile, elementMap)

  #  The basisMat is such that
  #    cartesianPosMatInAngstrom = posScale * directPosMat * basisMat
  # For an xyz file, we have only the cartesian coords
  # and no basis matrix.
  # Normally posScale = 1.0 (for Angstroms),
  # but for testing calcDist we use other values.

  coordType = 'cartesian'

  addReflections( bugLev, atoms, elementMap)

  bonds = calcBonds( bugLev, distType, posScale, basisMat, atoms)

  smolStg = formatSmol( bugLev, description, elementMap, coordType,
    posScale, basisMat, atoms, bonds)
  with open( outFile, 'w') as fout:
    fout.write( smolStg)




def addReflections( bugLev, atoms, elementMap):

  # When an atom coordinate is 0, add a matching
  # atom with that coordinate at 1.
  # When an atom coordinate is 1, add a matching
  # atom with that coordinate at 0.

  def reflectIt( atom, jj):
    if bugLev >= 5:
      print 'reflectIt: entry: jj: %d  atom: %s  directCoords: %s' \
        % (jj, atom, atom.directCoords,)
    if jj < 2: reflectIt( atom, jj+1)

    epsilon = 0.02
    incr = 0
    if abs( atom.directCoords[jj]) < epsilon: incr = 1
    elif abs( 1 - atom.directCoords[jj]) < epsilon: incr = -1

    if incr != 0:
      directCoords = copy.copy( atom.directCoords)
      directCoords[jj] += incr
      if directCoords[jj] < 0: directCoords[jj] = 0
      if directCoords[jj] > 1: directCoords[jj] = 1
      atomId = len( atoms)
      newAtom = Atom( atomId, atom.asym, directCoords, elementMap)
      newAtom.origAtom = atom
      atoms.append( newAtom)
      if bugLev >= 5:
        print '  reflectIt: jj: %d  atom: %s  reflect low  new id: %d' \
          % (jj, atom, len( atoms),)
      if jj < 2: reflectIt( newAtom, jj+1)

  natom = len( atoms)
  for ii in range(natom):
    reflectIt( atoms[ii], 0)







def calcBonds( bugLev, distType, posScale, basisMat, atoms):

  if atoms == None or len(atoms) < 2: bonds = []
  else: bonds = calcBondsSub( bugLev, distType, posScale, basisMat, atoms)
  return bonds




def calcBondsSub( bugLev, distType, posScale, basisMat, atoms):

  if type(basisMat).__name__ == 'list':
    basisMat = np.array( basisMat)

  norig = len( atoms)                    # num original atoms
  if basisMat.shape != (3,3): throwerr('basisMat is not 3x3')
  basisMatTranspose = basisMat.T         # transpose

  # Find all pairwise distances
  naug = len( atoms)          # num augmented atoms
  ndist = naug * (naug-1) / 2
  distances = ndist * [None]
  kk = 0
  for ia in range( naug):
    for ib in range( ia+1, naug):
      dist = calcDist(
        distType, posScale, basisMatTranspose,
        atoms[ia], atoms[ib])
      distances[kk] = (ia, ib, dist,)
      kk += 1

  # Sort by increasing distance
  distances.sort( cmp = lambda x, y: cmp( x[2], y[2]))

  avgDist = sum([dist[2] for dist in distances]) / ndist

  # Start with one cluster per atom
  clusters = naug * [None]
  for ii in range( naug):
    clusters[ii] = Cluster()
    clusters[ii].addAtom( atoms[ii])

  for ii in range( naug):
    cluster = clusters[ii]
    atom = cluster.atoms[0]
    if atom.origAtom != atom:
      origCluster = atom.origAtom.acluster
      origCluster.merge( cluster, 0)

  # For each distance, if the atoms are in different clusters,
  # join the two clusters.
  bonds = []                 # list of tuples (atoma, atomb, distance)
  for idist in range( ndist):
    (ia, ib, distance) = distances[idist]
    atoma = atoms[ia]
    atomb = atoms[ib]
    if atoma.acluster != atomb.acluster \
      and not(
        atoma.origAtom.numBond >= atoma.origAtom.maxBond or
        atomb.origAtom.numBond >= atomb.origAtom.maxBond):
      # Create new cluster by merging atoma, atomb clusters
      ca = atoma.acluster
      cb = atomb.acluster
      cnew = ca.merge( cb, distance)
      bonds.append( Bond(atoma, atomb, distance, ca, cb, cnew))

  if bugLev >= 1:
    print 'norig: %d  naug: %d' % (norig, naug,)
    if naug > 0:
      print '\nClusters'
      printCluster( atoms[0].acluster, 0)     # indent = 0

      print '\nBonds:'
      for bond in bonds:
        print bond

  return bonds










def printCluster( clus, indent):
  indstg = indent * '  '
  print '%s%s' % (indstg, clus,)
  if clus.kida != None: printCluster( clus.kida, indent + 1)
  if clus.kidb != None: printCluster( clus.kidb, indent + 1)












def readXyz( inFile, elementMap):

  with open( inFile) as fin:

    iline = 0
    # Get count, having format like:
    #    26
    (iline, line) = getLine( iline, fin)
    if line == None: throwerrLine('empty input file', iline, line)
    try: count = int( line)
    except ValueError, exc:
      throwerrLine('invalid count', iline, line)

    # Get description, having format like:
    #   icsd_098129 Co2 Cu4 O14 Sr4 Y2
    (iline, line) = getLine( iline, fin)
    if line == None: throwerrLine('invalid description', iline, line)
    description = line

    # Get coordinate lines, having format like:
    #   Co   0.2478457246260035  0.8330718276390030  0.4999011568620020
    atoms = []        # list of Atom
    while True:
      (iline, line) = getLine( iline, fin)
      if line == None: break
      toks = line.split()
      if len(toks) != 4: throwerrLine('invalid coord line', iline, line)
      atomSym = toks[0]
      atomSym = atomSym[0].upper() + atomSym[1:].lower()  # make case like 'Si'
      try: directCoords = map( float, toks[1:])
      except ValueError, exc:
        throwerrLine('invalid coord line', iline, line)
      atomId = len(atoms)
      atoms.append( Atom( atomId, atomSym, directCoords, elementMap))

  if len(atoms) != count:
    throwerr('count==%d != len(atoms)==%d' % (count, len(atoms),))
  return (description, atoms)





def formatSmol( bugLev, description, elementMap, coordType,
  posScale, basisMat, atoms, bonds):

  if type(basisMat).__name__ == 'list':
    basisMat = np.array( basisMat)

  # Make a map of element entries.  Each entry is a submap.
  # For a submap, convert an Element object with attributes
  # to a map with keys.
  jsonEleMap = {}
  syms = set( [atom.asym for atom in atoms])   # unique atom symbols
  for sym in syms:
    ele = elementMap[sym]
    keys = dir( ele)
    keys.sort()
    jele = {}
    for key in keys:
      if key.startswith('e'):
        jele[key] = getattr( ele, key)
    jsonEleMap[sym] = jele

  # Make JSON compatable structure for atoms
  jsonAtoms = []
  for atom in atoms:
    isReflection = False
    if atom.origAtom != atom: isReflection = True
    jatom = dict(
      aix = atom.aix,
      asym = atom.asym,
      directCoords = atom.directCoords,
      isReflection = isReflection)
    jsonAtoms.append( jatom)

  # Make JSON compatable structure for bonds
  jsonBonds = []
  for bond in bonds:
    jbond = [ bond.atoma.aix, bond.atomb.aix]
    jsonBonds.append( jbond)

  smol = dict(
    description = description,
    elementMap = jsonEleMap,
    coordType = coordType,
    posScale = posScale,
    basisMat = basisMat.tolist(),   # convert numpy array to list for JSON
    atoms = jsonAtoms,
    bonds = jsonBonds)

  smolStg = json.dumps( smol, sort_keys=True, indent=2, separators=(',', ': '))
  return smolStg











# cartesianPosMatInAngstrom = posScale * directPosMat * basisMat
#
# cartVec = posScale * basisMatTranspose * directVec

def calcDist(
  distType,
  posScale, 
  basisMatTranspose,
  atoma,
  atomb):

  directa = atoma.directCoords
  directb = atomb.directCoords

  # Convert to cartesian coords in Angstroms
  carta = posScale * np.dot( basisMatTranspose, directa)
  cartb = posScale * np.dot( basisMatTranspose, directb)

  # Calc distance between centers in Angstrom
  if len(carta) != 3 or len(cartb) != 3: throwerr('invalid directCoords')
  sumsq = 0
  for ii in range(len(carta)):
    sumsq += (carta[ii] - cartb[ii]) ** 2
  centerDist = math.sqrt( sumsq)

  # Subtract radii to get distance between shells
  eleMap = atoma.elementMap
  ra = 0.01 * eleMap[atoma.asym].eradiusAtomic_pm    # pm to Angstrom
  rb = 0.01 * eleMap[atomb.asym].eradiusAtomic_pm    # pm to Angstrom

  if distType == 'center': edgeDist = centerDist
  elif distType == 'shell':
    # Distance between spheres in Angstrom
    edgeDist = centerDist - ra - rb
    if edgeDist < 0: edgeDist = 0
  else: badparms('invalid distType: %s' % (distType,))
  return edgeDist








def getLine( iline, fin):
  line = fin.readline()    # includes final '\n'
  if line == '': line = None
  else:
    line = line.strip()
  iline += 1
  print '### getLine exit: iline: %d  line: %s' % (iline, line,)
  return (iline, line)



def throwerrLine( msg, iline, line):
  print '\nError: %s' % (msg,)
  print '  iline: %d' % (iline,)
  print '  line: %s' % (line,)
  sys.exit( 1)



def throwerr( msg):
  print '\nError: %s' % (msg,)
  sys.exit( 1)








class Element:
  def __init__( self,
    # Following values are from
    # http://en.wikipedia.org/wiki/List_of_elements
    # Missing value: -999
    enum,             # Atomic number                    for oxygen: 8
    esym,             # Atomic symbol                    for oxygen: 'O'
    ename,            # Name, 'Oxygen'
    egroup,           # Periodic table group (column)    for oxygen: 16
    eperiod,          # Periodic table period (row)      for oxygen: 2
    eweighta,         # Atomic weight, version A         for oxygen: 15.999
    edensity_g_cm3,   # Density, g/cm3                   for oxygen: 0.001429
    emelt_K,          # Melting point, K                 for oxygen: 54.36
    eboil_K,          # Boiling point, K                 for oxygen: 90.20
    eheatCap_J_gK,    # Specific heat capacity, J/gK     for oxygen: 0.918
    eelectroNega,     # Electronegativity, version A     for oxygen: 3.44
    eabundance_mg_kg, # Abundance in the earth's crust,
                      # mg/kg.                           for oxygen: 461000
                      # The special value "0.00099" means "<0.001".

    # Following values are from
    # http://en.wikipedia.org/wiki/List_of_elements_by_atomic_properties
    # Missing value: -999
    eweightb,         # Atomic weight, version B         for oxygen: 15.9994
    eelectroNegb,     # Electronegativity, version B     for oxygen: 3.44
    efirstIon_eV,     # First ionization energy, eV      for oxygen: 13.61806
    eradiusAtomic_pm, # Atomic radius, pm                for oxygen: 60
    erasiusVdw_pm,    # Van der Waals radius, pm         for oxygen: 152
    eradiusCov_pm,    # Covalent radius, pm              for oxygen: 73
    enumValence,      # Num valence electrons            for oxygen: 6

    # Following values are from
    # http://jmol.sourceforge.net/jscolors/
    ecolorHex,        # Color used by Jmol, integer      for oxygen: 0xFF0D0D
  ):
    self.enum = enum
    self.esym = esym
    self.ename = ename
    self.egroup = egroup
    self.eperiod = eperiod
    self.eweighta = eweighta
    self.edensity_g_cm3 = edensity_g_cm3
    self.emelt_K = emelt_K
    self.eboil_K = eboil_K
    self.eheatCap_J_gK = eheatCap_J_gK
    self.eelectroNega = eelectroNega
    self.eabundance_mg_kg = eabundance_mg_kg
    self.eweightb = eweightb
    self.eelectroNegb = eelectroNegb
    self.efirstIon_eV = efirstIon_eV
    self.eradiusAtomic_pm = eradiusAtomic_pm
    self.erasiusVdw_pm = erasiusVdw_pm
    self.eradiusCov_pm = eradiusCov_pm
    self.enumValence = enumValence
    self.ecolorHex = ecolorHex

  def __str__( self):
    res = self.esym
    return res

  def format( self):
    res = ''
    res += '  enum: %s\n' % (self.enum,)
    res += '  esym: %s\n' % (self.esym,)
    res += '  ename: %s\n' % (self.ename,)
    res += '  egroup: %s\n' % (self.egroup,)
    res += '  eperiod: %s\n' % (self.eperiod,)
    res += '  eweighta: %s\n' % (self.eweighta,)
    res += '  edensity_g_cm3: %s\n' % (self.edensity_g_cm3,)
    res += '  emelt_K: %s\n' % (self.emelt_K,)
    res += '  eboil_K: %s\n' % (self.eboil_K,)
    res += '  eheatCap_J_gK: %s\n' % (self.eheatCap_J_gK,)
    res += '  eelectroNega: %s\n' % (self.eelectroNega,)
    res += '  eabundance_mg_kg: %s\n' % (self.eabundance_mg_kg,)
    res += '  eweightb: %s\n' % (self.eweightb,)
    res += '  eelectroNegb: %s\n' % (self.eelectroNegb,)
    res += '  efirstIon_eV: %s\n' % (self.efirstIon_eV,)
    res += '  eradiusAtomic_pm: %s\n' % (self.eradiusAtomic_pm,)
    res += '  erasiusVdw_pm: %s\n' % (self.erasiusVdw_pm,)
    res += '  eradiusCov_pm: %s\n' % (self.eradiusCov_pm,)
    res += '  enumValence: %s\n' % (self.enumValence,)
    res += '  ecolorHex: 0x%06x\n' % (self.ecolorHex,)
    return res


def getElementMap():
  elements = [
    Element( 1  ,  "H"  ,  "Hydrogen"     ,  1   ,  1,  1.008      ,  0.00008988,  14.01   ,  20.28 ,  14.304,  2.20,  1400   ,  1.00794    ,  2.2 ,  13.59844,  25  ,  120 ,  38  ,  1   ,  0xFFFFFF ),
    Element( 2  ,  "He" ,  "Helium"       ,  18  ,  1,  4.002602   ,  0.0001785 ,  0.956   ,  4.22  ,  5.193 ,  -999,  0.008  ,  4.002602   ,  -999,  24.58741,  31  ,  140 ,  32  ,  2   ,  0xD9FFFF ),
    Element( 3  ,  "Li" ,  "Lithium"      ,  1   ,  2,  6.94       ,  0.534     ,  453.69  ,  1560  ,  3.582 ,  0.98,  20     ,  6.941      ,  0.98,  5.39172 ,  145 ,  182 ,  134 ,  1   ,  0xCC80FF ),
    Element( 4  ,  "Be" ,  "Beryllium"    ,  2   ,  2,  9.012182   ,  1.85      ,  1560    ,  2742  ,  1.825 ,  1.57,  2.8    ,  9.012182   ,  1.57,  9.3227  ,  105 ,  -999,  90  ,  2   ,  0xC2FF00 ),
    Element( 5  ,  "B"  ,  "Boron"        ,  13  ,  2,  10.81      ,  2.34      ,  2349    ,  4200  ,  1.026 ,  2.04,  10     ,  10.811     ,  2.04,  8.29803 ,  85  ,  -999,  82  ,  3   ,  0xFFB5B5 ),
    Element( 6  ,  "C"  ,  "Carbon"       ,  14  ,  2,  12.011     ,  2.267     ,  3800    ,  4300  ,  0.709 ,  2.55,  200    ,  12.0107    ,  2.55,  11.2603 ,  70  ,  170 ,  77  ,  4   ,  0x909090 ),
    Element( 7  ,  "N"  ,  "Nitrogen"     ,  15  ,  2,  14.007     ,  0.0012506 ,  63.15   ,  77.36 ,  1.04  ,  3.04,  19     ,  14.0067    ,  3.04,  14.53414,  65  ,  155 ,  75  ,  5   ,  0x3050F8 ),
    Element( 8  ,  "O"  ,  "Oxygen"       ,  16  ,  2,  15.999     ,  0.001429  ,  54.36   ,  90.20 ,  0.918 ,  3.44,  461000 ,  15.9994    ,  3.44,  13.61806,  60  ,  152 ,  73  ,  6   ,  0xFF0D0D ),
    Element( 9  ,  "F"  ,  "Fluorine"     ,  17  ,  2,  18.9984032 ,  0.001696  ,  53.53   ,  85.03 ,  0.824 ,  3.98,  585    ,  18.9984032 ,  3.98,  17.42282,  50  ,  147 ,  71  ,  7   ,  0x90E050 ),
    Element( 10 ,  "Ne" ,  "Neon"         ,  18  ,  2,  20.1797    ,  0.0008999 ,  24.56   ,  27.07 ,  1.03  ,  -999,  0.005  ,  20.10097   ,  -999,  21.5646 ,  38  ,  154 ,  69  ,  8   ,  0xB3E3F5 ),
    Element( 11 ,  "Na" ,  "Sodium"       ,  1   ,  3,  22.98976928,  0.971     ,  370.87  ,  1156  ,  1.228 ,  0.93,  23600  ,  22.98976928,  0.93,  5.13908 ,  180 ,  227 ,  154 ,  1   ,  0xAB5CF2 ),
    Element( 12 ,  "Mg" ,  "Magnesium"    ,  2   ,  3,  24.3050    ,  1.738     ,  923     ,  1363  ,  1.023 ,  1.31,  23300  ,  24.3050    ,  1.31,  7.64624 ,  150 ,  173 ,  130 ,  2   ,  0x8AFF00 ),
    Element( 13 ,  "Al" ,  "Aluminium"    ,  13  ,  3,  26.9815386 ,  2.698     ,  933.47  ,  2792  ,  0.897 ,  1.61,  82300  ,  26.9815386 ,  1.61,  5.98577 ,  125 ,  -999,  118 ,  3   ,  0xBFA6A6 ),
    Element( 14 ,  "Si" ,  "Silicon"      ,  14  ,  3,  28.085     ,  2.3296    ,  1687    ,  3538  ,  0.705 ,  1.9 ,  282000 ,  28.0855    ,  1.9 ,  8.15169 ,  110 ,  210 ,  111 ,  4   ,  0xF0C8A0 ),
    Element( 15 ,  "P"  ,  "Phosphorus"   ,  15  ,  3,  30.973762  ,  1.82      ,  317.30  ,  550   ,  0.769 ,  2.19,  1050   ,  30.973762  ,  2.19,  10.48669,  100 ,  180 ,  106 ,  5   ,  0xFF8000 ),
    Element( 16 ,  "S"  ,  "Sulfur"       ,  16  ,  3,  32.06      ,  2.067     ,  388.36  ,  717.87,  0.71  ,  2.58,  350    ,  32.065     ,  2.58,  10.36001,  100 ,  180 ,  102 ,  6   ,  0xFFFF30 ),
    Element( 17 ,  "Cl" ,  "Chlorine"     ,  17  ,  3,  35.45      ,  0.003214  ,  171.6   ,  239.11,  0.479 ,  3.16,  145    ,  35.453     ,  3.16,  12.96764,  100 ,  175 ,  99  ,  7   ,  0x1FF01F ),
    Element( 18 ,  "Ar" ,  "Argon"        ,  18  ,  3,  39.948     ,  0.0017837 ,  83.80   ,  87.30 ,  0.52  ,  -999,  3.5    ,  39.948     ,  -999,  15.75962,  71  ,  188 ,  97  ,  8   ,  0x80D1E3 ),
    Element( 19 ,  "K"  ,  "Potassium"    ,  1   ,  4,  39.0983    ,  0.862     ,  336.53  ,  1032  ,  0.757 ,  0.82,  20900  ,  39.0983    ,  0.82,  4.34066 ,  220 ,  275 ,  196 ,  1   ,  0x8F40D4 ),
    Element( 20 ,  "Ca" ,  "Calcium"      ,  2   ,  4,  40.078     ,  1.54      ,  1115    ,  1757  ,  0.647 ,  1   ,  41500  ,  40.078     ,  1   ,  6.11316 ,  180 ,  -999,  174 ,  2   ,  0x3DFF00 ),
    Element( 21 ,  "Sc" ,  "Scandium"     ,  3   ,  4,  44.955912  ,  2.989     ,  1814    ,  3109  ,  0.568 ,  1.36,  22     ,  44.955912  ,  1.36,  6.5615  ,  160 ,  -999,  144 ,  2   ,  0xE6E6E6 ),
    Element( 22 ,  "Ti" ,  "Titanium"     ,  4   ,  4,  47.867     ,  4.54      ,  1941    ,  3560  ,  0.523 ,  1.54,  5650   ,  47.867     ,  1.54,  6.8281  ,  140 ,  -999,  136 ,  2   ,  0xBFC2C7 ),
    Element( 23 ,  "V"  ,  "Vanadium"     ,  5   ,  4,  50.9415    ,  6.11      ,  2183    ,  3680  ,  0.489 ,  1.63,  120    ,  50.9415    ,  1.63,  6.7462  ,  135 ,  -999,  125 ,  2   ,  0xA6A6AB ),
    Element( 24 ,  "Cr" ,  "Chromium"     ,  6   ,  4,  51.9961    ,  7.15      ,  2180    ,  2944  ,  0.449 ,  1.66,  102    ,  51.9961    ,  1.66,  6.7665  ,  140 ,  -999,  127 ,  1   ,  0x8A99C7 ),
    Element( 25 ,  "Mn" ,  "Manganese"    ,  7   ,  4,  54.938045  ,  7.44      ,  1519    ,  2334  ,  0.479 ,  1.55,  950    ,  54.938045  ,  1.55,  7.43402 ,  140 ,  -999,  139 ,  2   ,  0x9C7AC7 ),
    Element( 26 ,  "Fe" ,  "Iron"         ,  8   ,  4,  55.845     ,  7.874     ,  1811    ,  3134  ,  0.449 ,  1.83,  56300  ,  55.845     ,  1.83,  7.9024  ,  140 ,  -999,  125 ,  2   ,  0xE06633 ),
    Element( 27 ,  "Co" ,  "Cobalt"       ,  9   ,  4,  58.933195  ,  8.86      ,  1768    ,  3200  ,  0.421 ,  1.88,  25     ,  58.933195  ,  1.91,  7.6398  ,  135 ,  163 ,  121 ,  2   ,  0xF090A0 ),
    Element( 28 ,  "Ni" ,  "Nickel"       ,  10  ,  4,  58.6934    ,  8.912     ,  1728    ,  3186  ,  0.444 ,  1.91,  84     ,  58.6934    ,  1.88,  7.881   ,  135 ,  -999,  126 ,  2   ,  0x50D050 ),
    Element( 29 ,  "Cu" ,  "Copper"       ,  11  ,  4,  63.546     ,  8.96      ,  1357.77 ,  2835  ,  0.385 ,  1.9 ,  60     ,  63.546     ,  1.9 ,  7.72638 ,  135 ,  140 ,  138 ,  1   ,  0xC88033 ),
    Element( 30 ,  "Zn" ,  "Zinc"         ,  12  ,  4,  65.38      ,  7.134     ,  692.88  ,  1180  ,  0.388 ,  1.65,  70     ,  65.38      ,  1.65,  9.3942  ,  135 ,  139 ,  131 ,  2   ,  0x7D80B0 ),
    Element( 31 ,  "Ga" ,  "Gallium"      ,  13  ,  4,  69.723     ,  5.907     ,  302.9146,  2477  ,  0.371 ,  1.81,  19     ,  69.723     ,  1.81,  5.9993  ,  130 ,  187 ,  126 ,  3   ,  0xC28F8F ),
    Element( 32 ,  "Ge" ,  "Germanium"    ,  14  ,  4,  72.63      ,  5.323     ,  1211.40 ,  3106  ,  0.32  ,  2.01,  1.5    ,  72.64      ,  2.01,  7.8994  ,  125 ,  -999,  122 ,  4   ,  0x668F8F ),
    Element( 33 ,  "As" ,  "Arsenic"      ,  15  ,  4,  74.92160   ,  5.776     ,  1090    ,  887   ,  0.329 ,  2.18,  1.8    ,  74.92160   ,  2.18,  9.7886  ,  115 ,  185 ,  119 ,  5   ,  0xBD80E3 ),
    Element( 34 ,  "Se" ,  "Selenium"     ,  16  ,  4,  78.96      ,  4.809     ,  453     ,  958   ,  0.321 ,  2.55,  0.05   ,  78.96      ,  2.55,  9.75238 ,  115 ,  190 ,  116 ,  6   ,  0xFFA100 ),
    Element( 35 ,  "Br" ,  "Bromine"      ,  17  ,  4,  79.904     ,  3.122     ,  265.8   ,  332.0 ,  0.474 ,  2.96,  2.4    ,  79.904     ,  2.96,  11.81381,  115 ,  185 ,  114 ,  7   ,  0xA62929 ),
    Element( 36 ,  "Kr" ,  "Krypton"      ,  18  ,  4,  83.798     ,  0.003733  ,  115.79  ,  119.93,  0.248 ,  3   ,  0.00099,  83.798     ,  3   ,  13.99961,  88  ,  202 ,  110 ,  8   ,  0x5CB8D1 ),
    Element( 37 ,  "Rb" ,  "Rubidium"     ,  1   ,  5,  85.4678    ,  1.532     ,  312.46  ,  961   ,  0.363 ,  0.82,  90     ,  85.4678    ,  0.82,  4.17713 ,  235 ,  -999,  211 ,  1   ,  0x702EB0 ),
    Element( 38 ,  "Sr" ,  "Strontium"    ,  2   ,  5,  87.62      ,  2.64      ,  1050    ,  1655  ,  0.301 ,  0.95,  370    ,  87.62      ,  0.95,  5.6949  ,  200 ,  -999,  192 ,  2   ,  0x00FF00 ),
    Element( 39 ,  "Y"  ,  "Yttrium"      ,  3   ,  5,  88.90585   ,  4.469     ,  1799    ,  3609  ,  0.298 ,  1.22,  33     ,  88.90585   ,  1.22,  6.2171  ,  180 ,  -999,  162 ,  2   ,  0x94FFFF ),
    Element( 40 ,  "Zr" ,  "Zirconium"    ,  4   ,  5,  91.224     ,  6.506     ,  2128    ,  4682  ,  0.278 ,  1.33,  165    ,  91.224     ,  1.33,  6.6339  ,  155 ,  -999,  148 ,  2   ,  0x94E0E0 ),
    Element( 41 ,  "Nb" ,  "Niobium"      ,  5   ,  5,  92.90638   ,  8.57      ,  2750    ,  5017  ,  0.265 ,  1.6 ,  20     ,  92.90638   ,  1.6 ,  6.75885 ,  145 ,  -999,  137 ,  1   ,  0x73C2C9 ),
    Element( 42 ,  "Mo" ,  "Molybdenum"   ,  6   ,  5,  95.96      ,  10.22     ,  2896    ,  4912  ,  0.251 ,  2.16,  1.2    ,  95.96      ,  2.16,  7.09243 ,  145 ,  -999,  145 ,  1   ,  0x54B5B5 ),
    Element( 43 ,  "Tc" ,  "Technetium"   ,  7   ,  5,  98         ,  11.5      ,  2430    ,  4538  ,  -999  ,  1.9 ,  0.00099,  98         ,  1.9 ,  7.28    ,  135 ,  -999,  156 ,  1   ,  0x3B9E9E ),
    Element( 44 ,  "Ru" ,  "Ruthenium"    ,  8   ,  5,  101.07     ,  12.37     ,  2607    ,  4423  ,  0.238 ,  2.2 ,  0.001  ,  101.07     ,  2.2 ,  7.3605  ,  130 ,  -999,  126 ,  1   ,  0x248F8F ),
    Element( 45 ,  "Rh" ,  "Rhodium"      ,  9   ,  5,  102.90550  ,  12.41     ,  2237    ,  3968  ,  0.243 ,  2.28,  0.001  ,  102.90550  ,  2.28,  7.4589  ,  135 ,  -999,  135 ,  1   ,  0x0A7D8C ),
    Element( 46 ,  "Pd" ,  "Palladium"    ,  10  ,  5,  106.42     ,  12.02     ,  1828.05 ,  3236  ,  0.244 ,  2.2 ,  0.015  ,  106.42     ,  2.2 ,  8.3369  ,  140 ,  163 ,  131 ,  -999,  0x006985 ),
    Element( 47 ,  "Ag" ,  "Silver"       ,  11  ,  5,  107.8682   ,  10.501    ,  1234.93 ,  2435  ,  0.235 ,  1.93,  0.075  ,  107.8682   ,  1.93,  7.5762  ,  160 ,  172 ,  153 ,  1   ,  0xC0C0C0 ),
    Element( 48 ,  "Cd" ,  "Cadmium"      ,  12  ,  5,  112.411    ,  8.69      ,  594.22  ,  1040  ,  0.232 ,  1.69,  0.159  ,  112.411    ,  1.69,  8.9938  ,  155 ,  158 ,  148 ,  2   ,  0xFFD98F ),
    Element( 49 ,  "In" ,  "Indium"       ,  13  ,  5,  114.818    ,  7.31      ,  429.75  ,  2345  ,  0.233 ,  1.78,  0.25   ,  114.818    ,  1.78,  5.78636 ,  155 ,  193 ,  144 ,  3   ,  0xA67573 ),
    Element( 50 ,  "Sn" ,  "Tin"          ,  14  ,  5,  118.710    ,  7.287     ,  505.08  ,  2875  ,  0.228 ,  1.96,  2.3    ,  118.710    ,  1.96,  7.3439  ,  145 ,  217 ,  141 ,  4   ,  0x668080 ),
    Element( 51 ,  "Sb" ,  "Antimony"     ,  15  ,  5,  121.760    ,  6.685     ,  903.78  ,  1860  ,  0.207 ,  2.05,  0.2    ,  121.760    ,  2.05,  8.6084  ,  145 ,  -999,  138 ,  5   ,  0x9E63B5 ),
    Element( 52 ,  "Te" ,  "Tellurium"    ,  16  ,  5,  127.60     ,  6.232     ,  722.66  ,  1261  ,  0.202 ,  2.1 ,  0.001  ,  127.60     ,  2.1 ,  9.0096  ,  140 ,  206 ,  135 ,  6   ,  0xD47A00 ),
    Element( 53 ,  "I"  ,  "Iodine"       ,  17  ,  5,  126.90447  ,  4.93      ,  386.85  ,  457.4 ,  0.214 ,  2.66,  0.45   ,  126.90447  ,  2.66,  10.45126,  140 ,  198 ,  133 ,  7   ,  0x940094 ),
    Element( 54 ,  "Xe" ,  "Xenon"        ,  18  ,  5,  131.293    ,  0.005887  ,  161.4   ,  165.03,  0.158 ,  2.6 ,  0.00099,  131.293    ,  2.6 ,  12.1298 ,  108 ,  216 ,  130 ,  8   ,  0x429EB0 ),
    Element( 55 ,  "Cs" ,  "Caesium"      ,  1   ,  6,  132.9054519,  1.873     ,  301.59  ,  944   ,  0.242 ,  0.79,  3      ,  132.9054519,  0.79,  3.8939  ,  260 ,  -999,  225 ,  1   ,  0x57178F ),
    Element( 56 ,  "Ba" ,  "Barium"       ,  2   ,  6,  137.327    ,  3.594     ,  1000    ,  2170  ,  0.204 ,  0.89,  425    ,  137.327    ,  0.89,  5.2117  ,  215 ,  -999,  198 ,  2   ,  0x00C900 ),
    Element( 57 ,  "La" ,  "Lanthanum"    ,  -999,  6,  138.90547  ,  6.145     ,  1193    ,  3737  ,  0.195 ,  1.1 ,  39     ,  138.90547  ,  1.1 ,  5.5769  ,  195 ,  -999,  169 ,  2   ,  0x70D4FF ),
    Element( 58 ,  "Ce" ,  "Cerium"       ,  -999,  6,  140.116    ,  6.77      ,  1068    ,  3716  ,  0.192 ,  1.12,  66.5   ,  140.116    ,  1.12,  5.5387  ,  185 ,  -999,  -999,  2   ,  0xFFFFC7 ),
    Element( 59 ,  "Pr" ,  "Praseodymium" ,  -999,  6,  140.90765  ,  6.773     ,  1208    ,  3793  ,  0.193 ,  1.13,  9.2    ,  140.90765  ,  1.13,  5.473   ,  185 ,  -999,  -999,  2   ,  0xD9FFC7 ),
    Element( 60 ,  "Nd" ,  "Neodymium"    ,  -999,  6,  144.242    ,  7.007     ,  1297    ,  3347  ,  0.19  ,  1.14,  41.5   ,  144.242    ,  1.14,  5.525   ,  185 ,  -999,  -999,  2   ,  0xC7FFC7 ),
    Element( 61 ,  "Pm" ,  "Promethium"   ,  -999,  6,  145        ,  7.26      ,  1315    ,  3273  ,  -999  ,  -999,  0.00099,  145        ,  -999,  5.582   ,  185 ,  -999,  -999,  2   ,  0xA3FFC7 ),
    Element( 62 ,  "Sm" ,  "Samarium"     ,  -999,  6,  150.36     ,  7.52      ,  1345    ,  2067  ,  0.197 ,  1.17,  7.05   ,  150.36     ,  1.17,  5.6436  ,  185 ,  -999,  -999,  2   ,  0x8FFFC7 ),
    Element( 63 ,  "Eu" ,  "Europium"     ,  -999,  6,  151.964    ,  5.243     ,  1099    ,  1802  ,  0.182 ,  1.2 ,  2      ,  151.964    ,  -999,  5.6704  ,  185 ,  -999,  -999,  2   ,  0x61FFC7 ),
    Element( 64 ,  "Gd" ,  "Gadolinium"   ,  -999,  6,  157.25     ,  7.895     ,  1585    ,  3546  ,  0.236 ,  1.2 ,  6.2    ,  157.25     ,  1.2 ,  6.1501  ,  180 ,  -999,  -999,  2   ,  0x45FFC7 ),
    Element( 65 ,  "Tb" ,  "Terbium"      ,  -999,  6,  158.92535  ,  8.229     ,  1629    ,  3503  ,  0.182 ,  1.2 ,  1.2    ,  158.92535  ,  -999,  5.8638  ,  175 ,  -999,  -999,  2   ,  0x30FFC7 ),
    Element( 66 ,  "Dy" ,  "Dysprosium"   ,  -999,  6,  162.500    ,  8.55      ,  1680    ,  2840  ,  0.17  ,  1.22,  5.2    ,  162.500    ,  1.22,  5.9389  ,  175 ,  -999,  -999,  2   ,  0x1FFFC7 ),
    Element( 67 ,  "Ho" ,  "Holmium"      ,  -999,  6,  164.93032  ,  8.795     ,  1734    ,  2993  ,  0.165 ,  1.23,  1.3    ,  164.93032  ,  1.23,  6.0215  ,  175 ,  -999,  -999,  2   ,  0x00FF9C ),
    Element( 68 ,  "Er" ,  "Erbium"       ,  -999,  6,  167.259    ,  9.066     ,  1802    ,  3141  ,  0.168 ,  1.24,  3.5    ,  167.259    ,  1.24,  6.1077  ,  175 ,  -999,  -999,  2   ,  0x00E675 ),
    Element( 69 ,  "Tm" ,  "Thulium"      ,  -999,  6,  168.93421  ,  9.321     ,  1818    ,  2223  ,  0.16  ,  1.25,  0.52   ,  168.93421  ,  1.25,  6.18431 ,  175 ,  -999,  -999,  2   ,  0x00D452 ),
    Element( 70 ,  "Yb" ,  "Ytterbium"    ,  -999,  6,  173.054    ,  6.965     ,  1097    ,  1469  ,  0.155 ,  1.1 ,  3.2    ,  173.054    ,  -999,  6.25416 ,  175 ,  -999,  -999,  2   ,  0x00BF38 ),
    Element( 71 ,  "Lu" ,  "Lutetium"     ,  3   ,  6,  174.9668   ,  9.84      ,  1925    ,  3675  ,  0.154 ,  1.27,  0.8    ,  174.9668   ,  1.27,  5.4259  ,  175 ,  -999,  160 ,  2   ,  0x00AB24 ),
    Element( 72 ,  "Hf" ,  "Hafnium"      ,  4   ,  6,  178.49     ,  13.31     ,  2506    ,  4876  ,  0.144 ,  1.3 ,  3      ,  178.49     ,  1.3 ,  6.82507 ,  155 ,  -999,  150 ,  2   ,  0x4DC2FF ),
    Element( 73 ,  "Ta" ,  "Tantalum"     ,  5   ,  6,  180.94788  ,  16.654    ,  3290    ,  5731  ,  0.14  ,  1.5 ,  2      ,  180.94788  ,  1.5 ,  7.5496  ,  145 ,  -999,  138 ,  2   ,  0x4DA6FF ),
    Element( 74 ,  "W"  ,  "Tungsten"     ,  6   ,  6,  183.84     ,  19.25     ,  3695    ,  5828  ,  0.132 ,  2.36,  1.3    ,  183.84     ,  2.36,  7.864   ,  135 ,  -999,  146 ,  2   ,  0x2194D6 ),
    Element( 75 ,  "Re" ,  "Rhenium"      ,  7   ,  6,  186.207    ,  21.02     ,  3459    ,  5869  ,  0.137 ,  1.9 ,  0.00099,  186.207    ,  1.9 ,  7.8335  ,  135 ,  -999,  159 ,  2   ,  0x267DAB ),
    Element( 76 ,  "Os" ,  "Osmium"       ,  8   ,  6,  190.23     ,  22.61     ,  3306    ,  5285  ,  0.13  ,  2.2 ,  0.002  ,  190.23     ,  2.2 ,  8.4382  ,  130 ,  -999,  128 ,  2   ,  0x266696 ),
    Element( 77 ,  "Ir" ,  "Iridium"      ,  9   ,  6,  192.217    ,  22.56     ,  2719    ,  4701  ,  0.131 ,  2.2 ,  0.001  ,  192.217    ,  2.2 ,  8.967   ,  135 ,  -999,  137 ,  2   ,  0x175487 ),
    Element( 78 ,  "Pt" ,  "Platinum"     ,  10  ,  6,  195.084    ,  21.46     ,  2041.4  ,  4098  ,  0.133 ,  2.28,  0.005  ,  195.084    ,  2.28,  8.9587  ,  135 ,  175 ,  128 ,  1   ,  0xD0D0E0 ),
    Element( 79 ,  "Au" ,  "Gold"         ,  11  ,  6,  196.966569 ,  19.282    ,  1337.33 ,  3129  ,  0.129 ,  2.54,  0.004  ,  196.966569 ,  2.54,  9.2255  ,  135 ,  166 ,  144 ,  1   ,  0xFFD123 ),
    Element( 80 ,  "Hg" ,  "Mercury"      ,  12  ,  6,  200.59     ,  13.5336   ,  234.43  ,  629.88,  0.14  ,  2   ,  0.085  ,  200.59     ,  2   ,  10.4375 ,  150 ,  155 ,  149 ,  2   ,  0xB8B8D0 ),
    Element( 81 ,  "Tl" ,  "Thallium"     ,  13  ,  6,  204.38     ,  11.85     ,  577     ,  1746  ,  0.129 ,  1.62,  0.85   ,  204.3833   ,  1.62,  6.1082  ,  190 ,  196 ,  148 ,  3   ,  0xA6544D ),
    Element( 82 ,  "Pb" ,  "Lead"         ,  14  ,  6,  207.2      ,  11.342    ,  600.61  ,  2022  ,  0.129 ,  2.33,  14     ,  207.2      ,  2.33,  7.41666 ,  180 ,  202 ,  147 ,  4   ,  0x575961 ),
    Element( 83 ,  "Bi" ,  "Bismuth"      ,  15  ,  6,  208.98040  ,  9.807     ,  544.7   ,  1837  ,  0.122 ,  2.02,  0.009  ,  208.98040  ,  2.02,  7.2856  ,  160 ,  -999,  146 ,  5   ,  0x9E4FB5 ),
    Element( 84 ,  "Po" ,  "Polonium"     ,  16  ,  6,  209        ,  9.32      ,  527     ,  1235  ,  -999  ,  2   ,  0.00099,  209        ,  2   ,  8.417   ,  190 ,  -999,  -999,  6   ,  0xAB5C00 ),
    Element( 85 ,  "At" ,  "Astatine"     ,  17  ,  6,  210        ,  7         ,  575     ,  610   ,  -999  ,  2.2 ,  0.00099,  210        ,  2.2 ,  -999    ,  -999,  -999,  -999,  7   ,  0x754F45 ),
    Element( 86 ,  "Rn" ,  "Radon"        ,  18  ,  6,  222        ,  0.00973   ,  202     ,  211.3 ,  0.094 ,  -999,  0.00099,  222        ,  -999,  10.7485 ,  120 ,  -999,  145 ,  8   ,  0x428296 ),
    Element( 87 ,  "Fr" ,  "Francium"     ,  1   ,  7,  223        ,  1.87      ,  300     ,  950   ,  -999  ,  0.7 ,  0.00099,  223        ,  0.7 ,  4.0727  ,  -999,  -999,  -999,  1   ,  0x420066 ),
    Element( 88 ,  "Ra" ,  "Radium"       ,  2   ,  7,  226        ,  5.5       ,  973     ,  2010  ,  -999  ,  0.9 ,  0.00099,  226        ,  0.9 ,  5.2784  ,  215 ,  -999,  -999,  2   ,  0x007D00 ),
    Element( 89 ,  "Ac" ,  "Actinium"     ,  -999,  7,  227        ,  10.07     ,  1323    ,  3471  ,  0.12  ,  1.1 ,  0.00099,  227        ,  1.1 ,  5.17    ,  195 ,  -999,  -999,  2   ,  0x70ABFA ),
    Element( 90 ,  "Th" ,  "Thorium"      ,  -999,  7,  232.03806  ,  11.72     ,  2115    ,  5061  ,  0.113 ,  1.3 ,  9.6    ,  232.03806  ,  1.3 ,  6.3067  ,  180 ,  -999,  -999,  2   ,  0x00BAFF ),
    Element( 91 ,  "Pa" ,  "Protactinium" ,  -999,  7,  231.03588  ,  15.37     ,  1841    ,  4300  ,  -999  ,  1.5 ,  0.00099,  231.03588  ,  1.5 ,  5.89    ,  180 ,  -999,  -999,  2   ,  0x00A1FF ),
    Element( 92 ,  "U"  ,  "Uranium"      ,  -999,  7,  238.02891  ,  18.95     ,  1405.3  ,  4404  ,  0.116 ,  1.38,  2.7    ,  238.02891  ,  1.38,  6.19405 ,  175 ,  186 ,  -999,  2   ,  0x008FFF ),
    Element( 93 ,  "Np" ,  "Neptunium"    ,  -999,  7,  237        ,  20.45     ,  917     ,  4273  ,  -999  ,  1.36,  0.00099,  237        ,  1.36,  6.2657  ,  175 ,  -999,  -999,  2   ,  0x0080FF ),
    Element( 94 ,  "Pu" ,  "Plutonium"    ,  -999,  7,  244        ,  19.84     ,  912.5   ,  3501  ,  -999  ,  1.28,  0.00099,  244        ,  1.28,  6.0262  ,  175 ,  -999,  -999,  2   ,  0x006BFF ),
    Element( 95 ,  "Am" ,  "Americium"    ,  -999,  7,  243        ,  13.69     ,  1449    ,  2880  ,  -999  ,  1.3 ,  0.00099,  243        ,  1.3 ,  5.9738  ,  175 ,  -999,  -999,  2   ,  0x545CF2 ),
    Element( 96 ,  "Cm" ,  "Curium"       ,  -999,  7,  247        ,  13.51     ,  1613    ,  3383  ,  -999  ,  1.3 ,  0.00099,  247        ,  1.3 ,  5.9915  ,  -999,  -999,  -999,  2   ,  0x785CE3 ),
    Element( 97 ,  "Bk" ,  "Berkelium"    ,  -999,  7,  247        ,  14.79     ,  1259    ,  -999  ,  -999  ,  1.3 ,  0.00099,  247        ,  1.3 ,  6.1979  ,  -999,  -999,  -999,  2   ,  0x8A4FE3 ),
    Element( 98 ,  "Cf" ,  "Californium"  ,  -999,  7,  251        ,  15.1      ,  1173    ,  -999  ,  -999  ,  1.3 ,  0.00099,  251        ,  1.3 ,  6.2817  ,  -999,  -999,  -999,  2   ,  0xA136D4 ),
    Element( 99 ,  "Es" ,  "Einsteinium"  ,  -999,  7,  252        ,  13.5      ,  1133    ,  -999  ,  -999  ,  1.3 ,  0      ,  252        ,  1.3 ,  6.42    ,  -999,  -999,  -999,  2   ,  0xB31FD4 ),
    Element( 100,  "Fm" ,  "Fermium"      ,  -999,  7,  257        ,  -999      ,  1800    ,  -999  ,  -999  ,  1.3 ,  0      ,  257        ,  1.3 ,  6.5     ,  -999,  -999,  -999,  2   ,  0xB31FBA ),
    Element( 101,  "Md" ,  "Mendelevium"  ,  -999,  7,  258        ,  -999      ,  1100    ,  -999  ,  -999  ,  1.3 ,  0      ,  258        ,  1.3 ,  6.58    ,  -999,  -999,  -999,  2   ,  0xB30DA6 ),
    Element( 102,  "No" ,  "Nobelium"     ,  -999,  7,  259        ,  -999      ,  1100    ,  -999  ,  -999  ,  1.3 ,  0      ,  259        ,  1.3 ,  6.65    ,  -999,  -999,  -999,  2   ,  0xBD0D87 ),
    Element( 103,  "Lr" ,  "Lawrencium"   ,  3   ,  7,  262        ,  -999      ,  1900    ,  -999  ,  -999  ,  1.3 ,  0      ,  262        ,  -999,  4.9     ,  -999,  -999,  -999,  3   ,  0xC70066 ),
    Element( 104,  "Rf" ,  "Rutherfordium",  4   ,  7,  267        ,  -999      ,  -999    ,  -999  ,  -999  ,  -999,  0      ,  261        ,  -999,  6       ,  -999,  -999,  -999,  -999,  0xCC0059 ),
    Element( 105,  "Db" ,  "Dubnium"      ,  5   ,  7,  268        ,  -999      ,  -999    ,  -999  ,  -999  ,  -999,  0      ,  262        ,  -999,  -999    ,  -999,  -999,  -999,  -999,  0xD1004F ),
    Element( 106,  "Sg" ,  "Seaborgium"   ,  6   ,  7,  269        ,  -999      ,  -999    ,  -999  ,  -999  ,  -999,  0      ,  263        ,  -999,  -999    ,  -999,  -999,  -999,  -999,  0xD90045 ),
    Element( 107,  "Bh" ,  "Bohrium"      ,  7   ,  7,  270        ,  -999      ,  -999    ,  -999  ,  -999  ,  -999,  0      ,  262        ,  -999,  -999    ,  -999,  -999,  -999,  -999,  0xE00038 ),
    Element( 108,  "Hs" ,  "Hassium"      ,  8   ,  7,  269        ,  -999      ,  -999    ,  -999  ,  -999  ,  -999,  0      ,  265        ,  -999,  -999    ,  -999,  -999,  -999,  -999,  0xE6002E ),
    Element( 109,  "Mt" ,  "Meitnerium"   ,  9   ,  7,  278        ,  -999      ,  -999    ,  -999  ,  -999  ,  -999,  0      ,  266        ,  -999,  -999    ,  -999,  -999,  -999,  -999,  0xEB0026 ),
    Element( 110,  "Ds" ,  "Darmstadtium" ,  10  ,  7,  281        ,  -999      ,  -999    ,  -999  ,  -999  ,  -999,  0      ,  269        ,  -999,  -999    ,  -999,  -999,  -999,  -999,  0xFF0000 ),
    Element( 111,  "Rg" ,  "Roentgenium"  ,  11  ,  7,  281        ,  -999      ,  -999    ,  -999  ,  -999  ,  -999,  0      ,  272        ,  -999,  -999    ,  -999,  -999,  -999,  -999,  0xFF0000 ),
    Element( 112,  "Cn" ,  "Copernicium"  ,  12  ,  7,  285        ,  -999      ,  -999    ,  -999  ,  -999  ,  -999,  0      ,  277        ,  -999,  -999    ,  -999,  -999,  -999,  -999,  0xFF0000 ),
    Element( 113,  "Uut",  "Ununtrium"    ,  13  ,  7,  286        ,  -999      ,  -999    ,  -999  ,  -999  ,  -999,  0      ,  283        ,  -999,  -999    ,  -999,  -999,  -999,  -999,  0xFF0000 ),
    Element( 114,  "Fl" ,  "Flerovium"    ,  14  ,  7,  289        ,  -999      ,  -999    ,  -999  ,  -999  ,  -999,  0      ,  285        ,  -999,  -999    ,  -999,  -999,  -999,  -999,  0xFF0000 ),
    Element( 115,  "Uup",  "Ununpentium"  ,  15  ,  7,  288        ,  -999      ,  -999    ,  -999  ,  -999  ,  -999,  0      ,  287        ,  -999,  -999    ,  -999,  -999,  -999,  -999,  0xFF0000 ),
    Element( 116,  "Lv" ,  "Livermorium"  ,  16  ,  7,  293        ,  -999      ,  -999    ,  -999  ,  -999  ,  -999,  0      ,  289        ,  -999,  -999    ,  -999,  -999,  -999,  -999,  0xFF0000 ),
    Element( 117,  "Uus",  "Ununseptium"  ,  17  ,  7,  294        ,  -999      ,  -999    ,  -999  ,  -999  ,  -999,  0      ,  291        ,  -999,  -999    ,  -999,  -999,  -999,  -999,  0xFF0000 ),
    Element( 118,  "Uuo",  "Ununoctium"   ,  18  ,  7,  294        ,  -999      ,  -999    ,  -999  ,  -999  ,  -999,  0      ,  293        ,  -999,  -999    ,  -999,  -999,  -999,  -999,  0xFF0000 ),
  ]

  print 'getElementMap: eles[0]:\n%s' % (elements[0].format(),)
  elementMap = {}
  for ele in elements:
    elementMap[ele.esym] = ele

  return elementMap


if __name__ == '__main__': main()
