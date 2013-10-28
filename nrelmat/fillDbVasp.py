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

import datetime, hashlib, json, os, re, sys, traceback
import numpy as np
import psycopg2

import readVasp
import wrapReceive
import wrapUpload


#====================================================================

vasprunName = 'vasprun.xml'
outcarName = 'OUTCAR'

#====================================================================


def badparms( msg):
  print '\nError: %s' % (msg,)
  print 'Parms:'
  print '  -bugLev      <int>      Debug level'
  print '  -func        <string>   createTableModel / createTableContrib'
  print '                          / fillTable'
  print '  -useCommit   <boolean>  false/true: do we commit changes to the DB.'
  print '  -deleteTable <boolean>  false/true: If func is create*, do we'
  print '                          delete the old table first.'
  print '  -archDir     <string>   Input dir tree'
  print '  -wrapId      <string>   Full uui or "first" or "last"'
  print '  -inSpec      <string>   JSON file containing parameters.'
  sys.exit(1)


#====================================================================


def main():
  '''
  Reads a dir tree and adds rows to the database table "model".
  The function is determined by the **-func** parameter; see below.

  This function is called by wrapReceive.py.

  Command line parameters:

  ================  =========    ==============================================
  Parameter         Type         Description
  ================  =========    ==============================================
  **-bugLev**       integer      Debug level.  Normally 0.
  **-func**         string       Function.  See below.
  **-useCommit**    boolean      false/true: do we commit changes to the DB.
  **-deleteTable**  boolean      false/true: If func is create*, do we
                                 delete the old table first.
  **-archDir**      string       Input dir tree.
  **-wrapId**       string       The unique id of this upload, created
                                 by wrapReceive.py from the uploaded file name.
                                 Or it can be "first" or "last", to use the
                                 first or last found uui.
  **-inSpec**       string       JSON file containing parameters.  See below.
  ================  =========    ==============================================

  **Values for the -func Parameter:**

  **createTableModel**
    Drop and create the model table.  In this case the -archDir
    and -wrapId parameters should be "none".

  **createTableContrib**
    Drop and recreate the contrib table.

  **fillTable**
    Read a dir tree and add rows to the database table "model".

  **inSpec File Parameters:**

  ===================    ==============================================
  Parameter              Description
  ===================    ==============================================
  **dbhost**             Database hostname.
  **dbport**             Database port number.
  **dbuser**             Database user name.
  **dbpswd**             Database password.
  **dbname**             Database database name.
  **dbschema**           Database schema name.
  **dbtablemodel**       Database name of the "model" table.
  **dbtablecontrib**     Database name of the "contrib" table.
  ===================    ==============================================

  **inSpec file example:**::

    {
      "dbhost"         : "scctest",
      "dbport"         : "6432",
      "dbuser"         : "x",
      "dbpswd"         : "x",
      "dbname"         : "cidlada",
      "dbschema"       : "satom",
      "dbtablemodel"   : "model",
      "dbtablecontrib" : "contrib"
    }

  '''

  bugLev      = None
  func        = None
  useCommit   = None
  deleteTable = None
  archDir     = None
  wrapId      = None
  inSpec      = None

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if   key == '-bugLev': bugLev = int( val)
    elif key == '-func': func = val
    elif key == '-useCommit':
      if val == 'false': useCommit = False
      elif val == 'true': useCommit = True
      else: badparms('invalid -useCommit arg')
    elif key == '-deleteTable':
      if val == 'false': deleteTable = False
      elif val == 'true': deleteTable = True
      else: badparms('invalid -deleteTable arg')
    elif key == '-archDir': archDir = val
    elif key == '-wrapId': wrapId = val
    elif key == '-inSpec': inSpec = val
    else: badparms('unknown key: "%s"' % (key,))

  if bugLev == None: badparms('parm not specified: -bugLev')
  if func == None: badparms('parm not specified: -func')
  if useCommit == None: badparms('parm not specified: -useCommit')
  if deleteTable == None: badparms('parm not specified: -deleteTable')
  if archDir == None: badparms('parm not specified: -archDir')
  if wrapId == None: badparms('parm not specified: -wrapId')
  if inSpec == None: badparms('parm not specified: -inSpec')

  if wrapId == 'first' or wrapId == 'last':
    wrapIdUse = None
    names = os.listdir( archDir)
    names.sort()
    for nm in names:
      if nm.endswith('.zzflag'):
        # If matches, returns (wrapId, adate, userid, hostname).
        wrapIdUse = wrapUpload.parseUui( nm)
        if wrapIdUse != None and wrapId == 'first': break
    if wrapIdUse == None:
      throwerr('wrapId is first or last, but no matching flag file found')

  else: wrapIdUse = wrapId

  fillDbVasp( bugLev, func, useCommit, deleteTable,
    archDir, wrapIdUse, inSpec)


#====================================================================



def fillDbVasp(
  bugLev,
  func,
  useCommit,
  deleteTable,
  archDir,
  wrapId,
  inSpec):
  '''
  Reads a dir tree and adds rows to the database table "model".

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.
  * func (str): Overall function.  One of the following:

      * ``'createTableModel'``
        Drop and create the model table.
      * ``'createTableContrib'``
        Drop and recreate the contrib table.
      * ``'fillTable'``
        Read a dir tree and add rows to the database table "model".

  * useCommit (boolean): If True, we commit changes to the DB.
  * deleteTable (boolean): If True and func is create\*,
    delete the specified table before creating it.
  * archDir (str): Input directory tree.
  * wrapId (str):
    The unique id of this upload, created
    by wrapReceive.py from the uploaded file name.
  * inSpec (str): Name of JSON file containing DB parameters.
                  See description at :func:`main`.

  **Returns**

  * None
  '''

  if bugLev >= 1:
    print 'fillDbVasp: func: %s' % (func,)
    print 'fillDbVasp: useCommit: %s' % (useCommit,)
    print 'fillDbVasp: deleteTable: %s' % (deleteTable,)
    print 'fillDbVasp: archDir: %s' % (archDir,)
    print 'fillDbVasp: wrapId: %s' % (wrapId,)
    print 'fillDbVasp: inSpec: %s' % (inSpec,)

  with open( inSpec) as fin:
    specMap = json.load( fin)

  dbhost   = specMap.get('dbhost', None)
  dbport   = specMap.get('dbport', None)
  dbuser   = specMap.get('dbuser', None)
  dbpswd   = specMap.get('dbpswd', None)
  dbname   = specMap.get('dbname', None)
  dbschema = specMap.get('dbschema', None)
  dbtablemodel   = specMap.get('dbtablemodel', None)
  dbtablecontrib = specMap.get('dbtablecontrib', None)

  if dbhost == None:   badparms('inSpec name not found: dbhost')
  if dbport == None:   badparms('inSpec name not found: dbport')
  if dbuser == None:   badparms('inSpec name not found: dbuser')
  if dbpswd == None:   badparms('inSpec name not found: dbpswd')
  if dbname == None:   badparms('inSpec name not found: dbname')
  if dbschema == None: badparms('inSpec name not found: dbschema')
  if dbtablemodel   == None: badparms('inSpec name not found: dbtablemodel')
  if dbtablecontrib == None: badparms('inSpec name not found: dbtablecontrib')
  dbport = int( dbport)

  if bugLev >= 1:
    print 'fillDbVasp: dbhost: %s' % (dbhost,)
    print 'fillDbVasp: dbport: %s' % (dbport,)
    print 'fillDbVasp: dbuser: %s' % (dbuser,)

  ##np.set_printoptions( threshold=10000)

  # Register psycopg2 adapter for np.ndarray
  # The function formatArray is defined below.
  def adaptVal( val):
    msg = formatArray( val)
    # AsIs provides getquoted() which just calls the wrapped object's str().
    return psycopg2.extensions.AsIs( msg)
  psycopg2.extensions.register_adapter( np.ndarray, adaptVal)
  psycopg2.extensions.register_adapter( np.float, adaptVal)
  psycopg2.extensions.register_adapter( np.float64, adaptVal)
  psycopg2.extensions.register_adapter( np.int64, adaptVal)
  psycopg2.extensions.register_adapter( np.string_, adaptVal)

  conn = None
  cursor = None
  try:
    conn = psycopg2.connect(
      host=dbhost,
      port=dbport,
      user=dbuser,
      password=dbpswd,
      database=dbname)
    cursor = conn.cursor()
    cursor.execute('set search_path to %s', (dbschema,))

    if func == 'createTableModel':
      createTableModel( bugLev, useCommit, deleteTable,
        conn, cursor, dbtablemodel)
    elif func == 'createTableContrib':
      createTableContrib( bugLev, useCommit, deleteTable,
        conn, cursor, dbtablecontrib)
    elif func == 'fillTable':
      fillTable( bugLev, useCommit, archDir, conn, cursor, wrapId,
        dbtablemodel, dbtablecontrib)
    else: throwerr('unknown func: "%s"' % (func,))

  finally:
    if cursor != None: cursor.close()
    if conn != None: conn.close()


#====================================================================


def createTableModel(
  bugLev,
  useCommit,
  deleteTable,
  conn,
  cursor,
  dbtablemodel):
  '''
  Creates the database table "model".

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.
  * useCommit (boolean): If True, we commit changes to the DB.
  * deleteTable (boolean): If True, delete the table before creating it.
  * conn (psycopg2.connection): Open DB connection
  * cursor (psycopg2.cursor): Open DB cursor
  * dbtablemodel (str): Database name of the "model" table.

  **Returns**

  * None
  '''

  if deleteTable:
    cursor.execute('DROP TABLE IF EXISTS %s' % (dbtablemodel,))
    if useCommit: conn.commit()

  cursor.execute('''
    CREATE TABLE %s (
      mident          serial,
      wrapid          text,
      abspath         text,   -- absolute path to dir
      relpath         text,   -- relative path below topDir

      -- Values derived from the directory path
      -- by wrapUpload.py getIcsdMap.
      -- Not stored in the database:
      --   statMap: map of fileName -> statInfoMap for files in this dir.

      icsdNum         int,   -- ICSD number in CIF file: _database_code_ICSD

      magType         text,  -- type of magnetic moment:
                             --   hsf:  hs-ferro.  magNum = 0.
                             --   hsaf: hs-anti-ferro.  magNum = test num.
                             --   lsf:  ls-ferro.  magNum = 0.
                             --   lsaf: ls-anti-ferro.  magNum = test num.
                             --   nm:   non-magnetic.  magNum = 0.
      magNum          int,   -- number of hs-anti-ferro or ls-anti-ferro test.

      relaxType       text,  -- Type of run:
                             --   std: standard,
                             --   rc:  relax_cellshape,
                             --   ri:  relax_ions
      relaxNum        int,   -- Folder num for rc or ri: 0, 1, ...

      excMsg          text,  -- exception msg from readVasp.py
      excTrace        text,  -- exception trace from readVasp.py
                             -- If excMsg != None,
                             -- all following fields are None.

      -- Values set by readVasp.py

      --- program, version, date etc ---
      runDate        timestamp,          -- 2013-03-11 10:07:01
      iterTotalTime  double precision,
      --- incar parameters ---
      systemName     text,               -- mos2_024000.cif
      encut_ev       double precision,   -- eV
      ibrion         int,
      isif           int,
      --- kpoints ---
      --- general parameters ---
      --- atom info ---
      numAtom        int,                -- == sum( typeNums)
      typeNames      text[],             -- ['Mo' 'S']
      typeNums       int[],              -- [2 4]
      typeMasses_amu float[],
      typePseudos    text[],
      typeValences   int[],
      atomNames      text[],
      atomMasses_amu float[],
      atomPseudos    text[],
      atomValences   int[],

      --- initial structure ---
      initialBasisMat         double precision[][],
      initialRecipBasisMat    double precision[][],
      initialCartPosMat       double precision[][],
      initialFracPosMat       double precision[][],

      --- final structure ---
      finalBasisMat           double precision[][],
      finalRecipBasisMat      double precision[][],
      finalCartPosMat         double precision[][],
      finalFracPosMat         double precision[][],

      --- final volume and density ---
      finalVolume_ang3        double precision,
      finalDensity_g_cm3      double precision,

      --- last calc forces ---
      finalForceMat_ev_ang         double precision[][],   -- eV/angstrom
      finalStressMat_kbar          double precision[][],   -- kbar
      finalPressure_kbar           double precision,       -- kbar

      --- eigenvalues and occupancies ---
      eigenMat                double precision[][],

      --- energy, efermi0 ---
      energyNoEntrp    double precision,   -- eV
      energyPerAtom  double precision,     -- eV
      efermi0        double precision,     -- eV
      --- cbMin, vbMax, bandgap ---
      cbMin          double precision,     -- eV
      vbMax          double precision,     -- eV
      bandgap        double precision,     -- eV

      -- Values set by augmentDb.py
      formula        text,     -- 'H2 O'
      chemtext       text,     -- ' H 2 O ', every token surrounded by spaces
      minenergyid    int,      -- mident w min energyperatom for this formula
      enthalpy       double precision,  -- FERE enthalpy of formation per atom

      --- metadata ---
      hashstring        text,     -- sha512 of our vasprun.xml
      meta_parents      text[],   -- sha512 of parent vasprun.xml, or null
      meta_firstName    text,     -- metadata: first name
      meta_lastName     text,     -- metadata: last name
      meta_publications text[],   -- metadata: publication DOI or placeholder
      meta_standards    text[],   -- metadata: controlled vocab keywords
      meta_keywords     text[],   -- metadata: uncontrolled vocab keywords
      meta_notes        text      -- metadata: notes
    )
  ''' % (dbtablemodel,))
  if useCommit: conn.commit()
  print 'fillDbVasp: table \"%s\" created' % (dbtablemodel,)

  ixName = '%s_mident_index' % (dbtablemodel,)
  cursor.execute('''
    CREATE INDEX %s ON %s (mident)
  ''' % (ixName, dbtablemodel,))
  if useCommit: conn.commit()
  print 'fillDbVasp: index \"%s\" created' % (ixName,)

  ixName = '%s_icsdnum_index' % (dbtablemodel,)
  cursor.execute('''
    CREATE INDEX %s ON %s (icsdnum)
  ''' % (ixName, dbtablemodel,))
  if useCommit: conn.commit()
  print 'fillDbVasp: index \"%s\" created' % (ixName,)




#====================================================================



def createTableContrib(
  bugLev,
  useCommit,
  deleteTable,
  conn,
  cursor,
  dbtablecontrib):
  '''
  Creates the database table "contrib".

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.
  * useCommit (boolean): If True, we commit changes to the DB.
  * deleteTable (boolean): If True, delete the table before creating it.
  * conn (psycopg2.connection): Open DB connection
  * cursor (psycopg2.cursor): Open DB cursor
  * dbtablecontrib (str): Database name of the "contrib" table.

  **Returns**

  * None
  '''

  if deleteTable:
    cursor.execute('DROP TABLE IF EXISTS %s' % (dbtablecontrib,))
    if useCommit: conn.commit()

  cursor.execute('''
    CREATE TABLE %s (
      wrapid       text,         -- wrapId for this upload
      curdate      timestamp,    -- date, time of this wrapId
      userid       text,         -- user id doing the upload
      hostname     text,         -- hostname of the upload
      topDir       text,         -- top level dir of the upload
      numkeptdir   int,          -- num of subdirs uploaded
      reldirs      text[]        -- list of relative subdirs
    )
  ''' % (dbtablecontrib,))
  if useCommit: conn.commit()

  print 'fillDbVasp: table \"%s\" created' % (dbtablecontrib,)

#====================================================================


# Add rows to the model table.
# Add one row to the contrib table.

def fillTable(
  bugLev,
  useCommit,
  archDir,
  conn,
  cursor,
  wrapId,
  dbtablemodel,
  dbtablecontrib):
  '''
  Adds rows to the model table, and one row to the contrib table.

  * Reads overMap from archdir/wrapId.json
  * For each dir in overMap['relDirs']:

      * Call fillRow to add one row to the model table.

  * Add one row to the contrib table representing this wrapId.


  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.
  * useCommit (boolean): If True, we commit changes to the DB.
  * archDir (str): Input directory tree.
  * conn (psycopg2.connection): Open DB connection
  * cursor (psycopg2.cursor): Open DB cursor
  * wrapId (str):
    The unique id of this upload, created
    by wrapReceive.py from the uploaded file name.
  * dbtablemodel (str): Database name of the "model" table.
  * dbtablecontrib (str): Database name of the "contrib" table.

  **Returns**

  * None
  '''

  if bugLev >= 1:
    print 'fillTable: archDir: %s' % (archDir,)
    print 'fillTable: wrapId: %s' % (wrapId,)

  if not os.path.isdir( archDir):
    throwerr('archDir is not a dir: "%s"' % (archDir,))

  subNames = os.listdir( archDir)
  subNames.sort()

  overFile = os.path.join( archDir, wrapId) + '.json'
  wrapUpload.checkFileFull( overFile)
  with open( overFile) as fin:
    overMap = json.load( fin)

  miscMap = overMap['miscMap']
  countMap = overMap['countMap']
  envMap = overMap['envMap']
  statInfos = overMap['statInfos']
  readType = overMap['readType']
  topDir = overMap['topDir']
  numKeptDir = overMap['numKeptDir']         # == len( relDirs)
  relDirs = overMap['relDirs']               # parallel array
  dirMaps = overMap['dirMaps']               # parallel array
  icsdMaps = overMap['icsdMaps']             # parallel array
  relFiles = overMap['relFiles']
  metadataForce = overMap['metadataForce']

  if bugLev >= 1:
    wrapUpload.printMap('fillTable: overMap', overMap, 100)
    wrapUpload.printMap('fillTable: miscMap', miscMap, 100)
    wrapUpload.printMap('fillTable: countMap', countMap, 100)
    wrapUpload.printMap('fillTable: envMap', envMap, 100)
    print 'fillTable: len( statInfos): %d' % (len( statInfos),)
    print 'fillTable: topDir: %s' % (topDir,)
    print 'fillTable: len( relDirs): %d' % (len( relDirs),)
    print 'fillTable: len( dirMaps): %d' % (len( dirMaps),)
    print 'fillTable: len( icsdMaps): %d' % (len( icsdMaps),)
    print 'fillTable: len( relFiles): %d' % (len( relFiles),)
    wrapUpload.printMap('fillTable: metadataForce', metadataForce, 100)

  # xxx delete?
  # Avoid duplicate rows if reprocessing data
  cursor.execute(
    'delete from ' + dbtablecontrib + ' where wrapid = %s',
    (wrapId,)
  )
  cursor.execute(
    'delete from ' + dbtablemodel + ' where wrapid = %s',
    (wrapId,)
  )
  if useCommit: conn.commit()

  # Add rows to the model table.
  for ii in range( len( relDirs)):
    try:
      fillRow(
        bugLev,
        useCommit,
        metadataForce,
        readType,
        archDir,
        topDir,
        relDirs[ii],            # parallel array
        dirMaps[ii],            # parallel array
        icsdMaps[ii],           # parallel array
        conn,
        cursor,
        wrapId,
        dbtablemodel)
    except Exception, exc:
      print 'readVasp.py.  caught exc: %s' % (repr(exc),)
      print '  dir:   "%s"' % (os.path.join( topDir, relDirs[ii]),)
      print '===== traceback start ====='
      print traceback.format_exc( limit=None)
      print '===== traceback end ====='

  # Add one row to the contrib table.
  # Coord with wrapUpload.py main.
  cursor.execute(
    '''
      insert into
    '''
    + dbtablecontrib + 
    ''' (
        wrapid,
        curdate,
        userid,
        hostname,
        topDir,
        numkeptdir,       -- == len( reldirs)
        reldirs)
        values (%s,%s,%s,%s,%s,%s,%s)
    ''',
    (
      wrapId,
      miscMap['curDate'],
      miscMap['userId'],
      miscMap['hostName'],
      topDir,
      numKeptDir,
      relDirs,
  ))
  
  if useCommit: conn.commit()


#====================================================================



def fillRow(
  bugLev,
  useCommit,
  metadataForce,
  readType,
  archDir,
  topDir,
  relDir,
  dirMap,
  icsdMap,
  conn,
  cursor,
  wrapId,
  dbtablemodel):
  '''
  Adds one row to the model table, corresponding to relDir.

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.
  * useCommit (boolean): If True, we commit changes to the DB.
  * metadataForce (map): If not None, force this to be the metadata
    map for all subDirs.
  * readType (str): If 'outcar', read the OUTCAR file.
    Else if 'xml', read the vasprun.xml file.
  * archDir (str): Input directory tree.
  * topDir (str): original top dir during upload.
  * relDir (str): sub directory under topDir (during wrapUpload.py) and
    under archDir (during wrapReceive.py and fillDb.py).

  * dirMap (map): map created by :mod:`wrapUpload` that contains:

      * absPath    : absolute path
      * relPath    : relative path
      * statMap    : map of fname -> file statistics for files in absPath.

  * icsdMap (map): map created by :mod:`wrapUpload` that contains:

      * icsdNum    : icsdNum, derived from file path
      * magType    : magType, derived from file path
      * magNum     : magNum, derived from file path
      * relaxType  : relaxType, derived from file path
      * relaxNum   : relaxNum, derived from file path

  * conn (psycopg2.connection): Open DB connection
  * cursor (psycopg2.cursor): Open DB cursor
  * wrapId (str):
    The unique id of this upload, created
    by wrapReceive.py from the uploaded file name.
  * dbtablemodel (str): Database name of the "model" table.

  **Returns**

  * None
  '''

  subPath = os.path.join( archDir, wrapReceive.vdirName, relDir)
  print 'fillRow: adding relDir: %s' % ( relDir,)
  if bugLev >= 1:
    print 'fillRow: wrapId: %s' % (wrapId,)
    print 'fillRow: subPath: %s' % (subPath,)
  if bugLev >= 5:
    wrapUpload.printMap('fillRow: dirMap', dirMap, 100)
    wrapUpload.printMap('fillRow: icsdMap', icsdMap, 100)

  # Check redDir and absPath
  if dirMap['relPath'] != relDir:
    throwerr('relPath mismatch.  old: "%s"  new: "%s"' \
      % (dirMap['relPath'], relDir,))
  absPath = os.path.join( topDir, relDir)
  if dirMap['absPath'] != absPath:
    throwerr('absPath mismatch.  old: "%s"  new: "%s"' \
      % (dirMap['absPath'], absPath,))

  if metadataForce == None:
    mpath = os.path.join( subPath, wrapUpload.metadataName)
    metaMap = wrapUpload.parseMetadata( mpath)
  else:
    metaMap = metadataForce
  if bugLev >= 5:
    wrapUpload.printMap('fillRow: metaMap', metaMap, 100)

  # Get the hash digest of vasprun.xml or OUTCAR
  if readType == 'outcar': tname = outcarName
  elif readType == 'xml': tname = vasprunName
  else: throwerr('invalid readType: %s' % (readType,))
  vname = os.path.join( subPath, tname)
  hash = hashlib.sha512()
  with open( vname) as fin:
    while True:
      stg = fin.read( 10000)
      if stg == '': break
      hash.update( stg)
  hashString = hash.hexdigest()

  # Check that our hashString is not in the database
  cursor.execute( 'SELECT mident, relpath FROM ' + dbtablemodel
    + ' WHERE hashString = %s', (hashString,))
  msg = cursor.statusmessage
  if msg != 'SELECT': throwerr('bad statusmessage')
  rows = cursor.fetchall()
  if len(rows) > 0:
    # xxx find a way to recover.  Don't throwerr.
    msg = 'Duplicate hashString.\n'
    msg += '  hashString: %s\n'  % (hashString,)
    for ii in range(len(rows)):
      msg += '  old mident: %s\n'  % (rows[ii][0],)
      msg += '  old relPath: %s\n' % (rows[ii][1],)
      msg += '\n'
    msg += '  new wrapId: %s\n' % (wrapId,)
    msg += '  new relDir: %s\n' % (relDir,)
    throwerr( msg)


  # Check that parent hashString is in the database
  if metaMap.has_key('parent'):
    for parentHash in metaMap['parent']:
      cursor.execute( 'SELECT mident, relpath FROM ' + dbtablemodel
        + ' WHERE hashString = %s', (parentHash,))
      msg = cursor.statusmessage
      if msg != 'SELECT': throwerr('bad statusmessage')
      rows = cursor.fetchall()
      if len(rows) != 1:
        msg = 'Parent hashString not found in DB.\n'
        msg += '  wrapId: %s\n' % (wrapId,)
        msg += '  relDir: %s\n' % (relDir,)
        msg += '  our hashString: %s\n' % (hashString,)
        msg += '  parent hashString: %s\n' % (parentHash,)
        throwerr( msg)

  # Read and parse vasprun.xml
  vaspObj = readVasp.parseDir( bugLev, readType, subPath, -1)  # print = -1

  typeNums = getattr( vaspObj, 'typeNums', None)
  numAtom = None
  if typeNums != None: numAtom = sum( typeNums)

  energyNoEntrp = getattr( vaspObj, 'energyNoEntrp', None)
  energyPerAtom = None
  if numAtom != None and energyNoEntrp != None:
    energyPerAtom = energyNoEntrp / numAtom

  cursor.execute(
    '''
      insert into
    '''
    + dbtablemodel + 
    ''' (
        wrapid,
        abspath,
        relpath,
        icsdNum,
        magType,
        magNum,
        relaxType,
        relaxNum,
        excMsg,
        excTrace,
        runDate,
        iterTotalTime,
        systemName,
        encut_ev,
        ibrion,
        isif,
        numAtom,
        typeNames,
        typeNums,
        typeMasses_amu,
        typePseudos,
        typeValences,
        atomNames,
        atomMasses_amu,
        atomPseudos,
        atomValences,
        initialBasisMat,
        initialRecipBasisMat,
        initialCartPosMat,
        initialFracPosMat,
        finalBasisMat,
        finalRecipBasisMat,
        finalCartPosMat,
        finalFracPosMat,
        finalVolume_ang3,
        finalDensity_g_cm3,
        finalForceMat_ev_ang,
        finalStressMat_kbar,
        finalPressure_kbar,
        eigenMat,
        energyNoEntrp,
        energyPerAtom,
        efermi0,
        cbMin,
        vbMax,
        bandgap,
        hashstring,        -- sha512 of our vasprun.xml

        meta_parents,      -- sha512 of parent vasprun.xml, or null
        meta_firstName,    -- metadata: first name
        meta_lastName,     -- metadata: last name
        meta_publications, -- metadata: publication DOI or placeholder
        meta_standards,    -- metadata: controlled vocab keywords
        meta_keywords,     -- metadata: uncontrolled vocab keywords
        meta_notes)        -- metadata: notes

      values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ''',
    ( wrapId,
      absPath,
      relDir,
      icsdMap.get('icsdNum', None),
      icsdMap.get('magType', None),
      icsdMap.get('magNum', None),
      icsdMap.get('relaxType', None),
      icsdMap.get('relaxNum', None),
      vaspObj.excMsg,
      vaspObj.excTrace,
      getattr( vaspObj, 'runDate', None),
      getattr( vaspObj, 'iterTotalTime', None),
      getattr( vaspObj, 'systemName', None),
      getattr( vaspObj, 'encut_ev', None),
      getattr( vaspObj, 'ibrion', None),
      getattr( vaspObj, 'isif', None),
      numAtom,
      getattr( vaspObj, 'typeNames', None),
      getattr( vaspObj, 'typeNums', None),
      getattr( vaspObj, 'typeMasses_amu', None),
      getattr( vaspObj, 'typePseudos', None),
      getattr( vaspObj, 'typeValences', None),
      getattr( vaspObj, 'atomNames', None),
      getattr( vaspObj, 'atomMasses_amu', None),
      getattr( vaspObj, 'atomPseudos', None),
      getattr( vaspObj, 'atomValences', None),
      getattr( vaspObj, 'initialBasisMat', None),
      getattr( vaspObj, 'initialRecipBasisMat', None),
      getattr( vaspObj, 'initialCartPosMat', None),
      getattr( vaspObj, 'initialFracPosMat', None),
      getattr( vaspObj, 'finalBasisMat', None),
      getattr( vaspObj, 'finalRecipBasisMat', None),
      getattr( vaspObj, 'finalCartPosMat', None),
      getattr( vaspObj, 'finalFracPosMat', None),
      getattr( vaspObj, 'finalVolume_ang3', None),
      getattr( vaspObj, 'finalDensity_g_cm3', None),
      getattr( vaspObj, 'finalForceMat_ev_ang', None),
      getattr( vaspObj, 'finalStressMat_kbar', None),
      getattr( vaspObj, 'finalPressure_kbar', None),
      getattr( vaspObj, 'eigenMat', None),
      getattr( vaspObj, 'energyNoEntrp', None),
      energyPerAtom,
      getattr( vaspObj, 'efermi0', None),
      getattr( vaspObj, 'cbMin', None),
      getattr( vaspObj, 'vbMax', None),
      getattr( vaspObj, 'bandgap', None),
      hashString,
      metaMap.get('parents', None),
      metaMap['firstName'],
      metaMap['lastName'],
      metaMap['publications'],
      metaMap['standards'],
      metaMap['keywords'],
      metaMap['notes'],
  ))
  if useCommit: conn.commit()




#====================================================================


# xxx: special case for None? ... format as NULL?

def formatArray( val):
  '''
  Formats a Python array into SQL format.

  Recursively formats a Python array, so
  the Python array `` [[11.1, 22.2], [33.3, 44.4]]``
  is formatted into the string:
  ``'array[array[11.1,22.2],array[33.3,44.4]]'``

  **Parameters**:

  * vec (float[] or float[][] or ...): Python array.  May be multidimensional.

  **Returns**

  * Formatted array as a str.
  '''

  if isinstance( val, np.ndarray):
    msg = 'array['
    for ii in range(len(val)):
      if ii > 0: msg += ','
      msg += formatArray( val[ii])       # recursion
    msg += ']'
  elif isinstance( val, float) \
    or isinstance( val, np.float) \
    or isinstance( val, np.float64):
    msg = '%s' % ( val,)
  elif isinstance( val, int): msg = '%d' % ( val,)
  elif isinstance( val, str):
    # http://www.postgresql.org/docs/9.2/static/sql-syntax-lexical.html#SQL-SYNTAX-CONSTANTS
    # http://www.postgresql.org/message-id/01fc01cc5653$b1b95810$152c0830$@mail.ru
    # Caution on testing: select arrayConstant is more permissive
    # than update.
    # select array[ E'b\'e"ta'];
    # update taba set svec =  array[E'alp\\h"a\'s'];
    # update taba set svec = $${gammas,\"\'delta}$$;

    msg = '%s' % ( val,)
    msg = msg.replace('\\', '\\\\')     # replace \ with \\
    msg = msg.replace('"',  '\\"')      # replace " with \"
    msg = msg.replace('\'', '\\\'')     # replace ' with \'
    msg = 'E\'' + msg + '\''            # use escaped strings
  else: throwerr('unknown type: %s for operand: %s' % (type(val), val,))
  return msg


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

