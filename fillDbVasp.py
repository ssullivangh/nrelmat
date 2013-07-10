#!/usr/bin/env python

import datetime, json, os, re, sys
import numpy as np
import psycopg2

import wrapUpload
import readVasp



#====================================================================


def badparms( msg):
  print '\nError: %s' % (msg,)
  print 'Parms:'
  print '  -bugLev     <int>      debug level'
  print '  -func       <string>   createTableModel / createTableContrib'
  print '                         / fillTable'
  print '  -archDir    <string>   input dir tree'
  print '  -wrapId     <string>'
  print '  -inSpec     <string>   inSpecJsonFile'
  sys.exit(1)


#====================================================================


def main():
  '''
  Read a dir tree and add rows to the database table "model".
  The function is determined by the **-func** parameter; see below.

  This function is called by wrapReceive.py.

  Command line parameters:

  ==============   =========    ==============================================
  Parameter        Type         Description
  ==============   =========    ==============================================
  **-bugLev**      integer      Debug level.  Normally 0.
  **-func**        string       Function.  See below.
  **-archDir**     string       Input dir tree.
  **-wrapId**      string       The unique id of this upload, created
                                by wrapReceive.py from the uploaded file name.
  **-inSpec**      string       JSON file containing parameters.  See below.
  ==============   =========    ==============================================

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

  bugLev   = None
  func     = None
  archDir  = None
  wrapId   = None
  inSpec   = None

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if   key == '-bugLev': bugLev = int( val)
    elif key == '-func': func = val
    elif key == '-archDir': archDir = val
    elif key == '-wrapId': wrapId = val
    elif key == '-inSpec': inSpec = val
    else: badparms('unknown key: "%s"' % (key,))

  if bugLev == None: badparms('parm not specified: -bugLev')
  if func == None: badparms('parm not specified: -func')
  if archDir == None: badparms('parm not specified: -archDir')
  if wrapId == None: badparms('parm not specified: -wrapId')
  if inSpec == None: badparms('parm not specified: -inSpec')

  fillDbVasp( bugLev, func, archDir, wrapId, inSpec)


#====================================================================



def fillDbVasp(
  bugLev,
  func,
  archDir,
  wrapId,
  inSpec):

  if bugLev >= 1:
    print 'fillDbVasp: func: %s' % (func,)
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
      createTableModel( bugLev, conn, cursor, dbtablemodel)
    elif func == 'createTableContrib':
      createTableContrib( bugLev, conn, cursor, dbtablecontrib)
    elif func == 'fillTable':
      fillTable( bugLev, archDir, conn, cursor, wrapId,
        dbtablemodel, dbtablecontrib)
    else: throwerr('unknown func: "%s"' % (func,))
  finally:
    if cursor != None: cursor.close()
    if conn != None: conn.close()


#====================================================================


def createTableModel(
  bugLev,
  conn,
  cursor,
  dbtablemodel):

  cursor.execute('drop table if exists %s' % (dbtablemodel,))
  conn.commit()

  cursor.execute('''
    CREATE TABLE %s (
      mident          serial,
      wrapid          text,
      abspath         text,
      relpath         text,
      statmapjson     text,

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
      initialCartesianPosMat  double precision[][],
      initialDirectPosMat     double precision[][],

      --- final structure ---
      finalBasisMat           double precision[][],
      finalRecipBasisMat      double precision[][],
      finalCartesianPosMat    double precision[][],
      finalDirectPosMat       double precision[][],

      --- final volume and density ---
      finalVolumeVasp_ang3    double precision,
      density_g_cm3           double precision,

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

      --- columns filled by augmentDb.py ---
      isminenergy    boolean,
      chemsum        text,              -- 'H2 O'
      chemform       text               -- ' H 2 O '
                                        -- every token surrounded by spaces
    )
  ''' % (dbtablemodel,))
  conn.commit()
  print 'fillDbVasp: table \"%s\" created' % (dbtablemodel,)

  ixName = '%s_mident_index' % (dbtablemodel,)
  cursor.execute('''
    CREATE INDEX %s ON %s (mident)
  ''' % (ixName, dbtablemodel,))
  conn.commit()
  print 'fillDbVasp: index \"%s\" created' % (ixName,)




#====================================================================



def createTableContrib(
  bugLev,
  conn,
  cursor,
  dbtablecontrib):

  cursor.execute('drop table if exists %s' % (dbtablecontrib,))
  conn.commit()

  cursor.execute('''
    CREATE TABLE %s (
      wrapid       text,
      curdate      timestamp,
      userid       text,
      hostname     text,
      uploaddir    text,
      reldirs      text[],
      archpaths    text[],
      fnd_incar    int,
      tot_incar    int,
      fnd_kpoints    int,
      tot_kpoints    int,
      fnd_poscar    int,
      tot_poscar    int,
      fnd_potcar    int,
      tot_potcar    int,
      fnd_outcar    int,
      tot_outcar    int,
      fnd_vasprun    int,
      tot_vasprun    int,
      meta_firstname   text,     -- metadata: author first name
      meta_lastname    text,     -- metadata: author last name
      meta_publication text,     -- metadata: publication DOI or placeholder
      meta_standards   text[],   -- metadata: controlled vocab keywords
      meta_keywords    text[],   -- metadata: uncontrolled vocab keywords
      meta_notes       text,     -- metadata: notes
      meta_omit        text[]    -- metadata: omit patterns
    )
  ''' % (dbtablecontrib,))
  conn.commit()

  print 'fillDbVasp: table \"%s\" created' % (dbtablecontrib,)

#====================================================================


# Add rows to the model table.
# Add one row to the contrib table.

def fillTable(
  bugLev,
  archDir,
  conn,
  cursor,
  wrapId,
  dbtablemodel,
  dbtablecontrib):

  if bugLev >= 1:
    print 'fillTable: archDir: %s' % (archDir,)
    print 'fillTable: wrapId: %s' % (wrapId,)

  if not os.path.isdir( archDir):
    throwerr('archDir is not a dir: "%s"' % (archDir,))

  subNames = os.listdir( archDir)
  subNames.sort()

  digestDir = os.path.join( archDir, wrapUpload.digestDirName)
  jFile = os.path.join( digestDir, wrapUpload.overMapFile)
  wrapUpload.checkFileFull( jFile)
  with open( jFile) as fin:
    overMap = json.load( fin)

  metaMap = overMap['metaMap']
  miscMap = overMap['miscMap']

  if bugLev >= 1:
    printMap('fillTable: overMap', overMap, 30)
    printMap('fillTable: metaMap', metaMap, 30)
    printMap('fillTable: miscMap', miscMap, 30)

  # Avoid duplicate rows if reprocessing data
  cursor.execute(
    'delete from ' + dbtablecontrib + ' where wrapid = %s',
    (wrapId,)
  )
  cursor.execute(
    'delete from ' + dbtablemodel + ' where wrapid = %s',
    (wrapId,)
  )
  conn.commit()

  # Add rows to the model table.
  fillTableSub(
    bugLev,
    archDir,
    conn,
    cursor,
    wrapId,
    dbtablemodel)

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
        uploaddir,
        reldirs,
        archpaths,
        fnd_incar,
        tot_incar,
        fnd_kpoints,
        tot_kpoints,
        fnd_poscar,
        tot_poscar,
        fnd_potcar,
        tot_potcar,
        fnd_outcar,
        tot_outcar,
        fnd_vasprun,
        tot_vasprun,
        meta_firstname,    -- metadata: author first name
        meta_lastname,     -- metadata: author last name
        meta_publication,  -- metadata: publication DOI or placeholder
        meta_standards,    -- metadata: controlled vocab keywords
        meta_keywords,     -- metadata: uncontrolled vocab keywords
        meta_notes,        -- metadata: notes
        meta_omit)         -- metadata: omit patterns

        values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ''',
    (
      wrapId,
      overMap['curDate'],
      overMap['userId'],
      overMap['hostName'],
      overMap['uploadDir'],
      overMap['relDirs'],
      overMap['archPaths'],

      miscMap['fnd_INCAR'],
      miscMap['tot_INCAR'],
      miscMap['fnd_KPOINTS'],
      miscMap['tot_KPOINTS'],
      miscMap['fnd_POSCAR'],
      miscMap['tot_POSCAR'],
      miscMap['fnd_POTCAR'],
      miscMap['tot_POTCAR'],
      miscMap['fnd_OUTCAR'],
      miscMap['tot_OUTCAR'],
      miscMap['fnd_vasprun.xml'],
      miscMap['tot_vasprun.xml'],

      metaMap['firstName'],
      metaMap['lastName'],
      metaMap['publication'],
      metaMap['standards'],
      metaMap['keywords'],
      metaMap['notes'],
      metaMap['omit'],
  ))
  
  conn.commit()


#====================================================================


# Add rows to the model table.

def fillTableSub(
  bugLev,
  inDir,
  conn,
  cursor,
  wrapId,
  dbtablemodel):

  if bugLev >= 1:
    print 'fillTableSub: wrapId: %s' % (wrapId,)
    print 'fillTableSub: inDir: %s' % (inDir,)

  if not os.path.isdir( inDir):
    throwerr('inDir is not a dir: "%s"' % (inDir,))

  subNames = os.listdir( inDir)
  subNames.sort()

  if wrapUpload.smallMapFile in subNames:
    fillDbRow( bugLev, inDir, conn, cursor, wrapId, dbtablemodel)

  # Recursion on subdirs
  for nm in subNames:
    subPath = os.path.join( inDir, nm)
    if os.path.isdir( subPath):
      fillTableSub(
        bugLev,
        subPath,
        conn,
        cursor,
        wrapId,
        dbtablemodel)





#xxx all print, all xxx
#xxx del digest*
#xxx make sure we can repeatedly upload one dir.


#====================================================================



def fillDbRow(
  bugLev,
  subPath,
  conn,
  cursor,
  wrapId,
  dbtablemodel):

  if bugLev >= 1:
    print 'fillDbRow: wrapId: %s' % (wrapId,)
    print 'fillDbRow: subPath: %s' % (subPath,)

  print 'fillDbRow: adding subPath: %s' % ( subPath,)

  ourJsonPath = os.path.join( subPath, wrapUpload.smallMapFile)
  if bugLev >= 5: print 'fillDbRow: ourJsonPath: %s' % (ourJsonPath,)

  wrapUpload.checkFileFull( ourJsonPath)
  with open( ourJsonPath) as fin:
    smallMap = json.load( fin)

  if bugLev >= 5:
    printMap('fillTableSub: smallMap', smallMap, 30)

  readType = 'xml'
  vaspObj = readVasp.parseDir( bugLev, readType, subPath, -1)  # print = -1
  if bugLev >= 5:
    keys = smallMap.keys()
    keys.sort()
    print 'fillDbRow: smallMap keys: %s' % (keys,)

  typeNums = getattr( vaspObj, 'typeNums', None)
  numAtom = None
  if typeNums != None: numAtom = sum( typeNums)

  energyNoEntrp = getattr( vaspObj, 'energyNoEntrp', None)
  energyPerAtom = None
  if numAtom != None and energyNoEntrp != None:
    energyPerAtom = energyNoEntrp / numAtom

  ## Avoid duplicate rows if reprocessing data
  #cursor.execute(
  #  'delete from ' + dbtablemodel
  #    + ' where wrapid = %s and path = %s and icsdnum = %s'
  #    + ' and magtype = %s and magnum = %s'
  #    + ' and relaxType = %s and relaxNum = %s'
  #    + ' and runDate = %s and iterTotalTime = %s'
  #    + ' and systemName = %s',
  #  (wrapid, path, icsdNum, magType, magNum,
  #  relaxTtype, relaxNum, runDate, iterTotalTime, systemName,)
  #)
  #conn.commit()

  cursor.execute(
    '''
      insert into
    '''
    + dbtablemodel + 
    ''' (
        wrapid,
        abspath,
        relpath,
        statmapjson,

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
        initialCartesianPosMat,
        initialDirectPosMat,

        finalBasisMat,
        finalRecipBasisMat,
        finalCartesianPosMat,
        finalDirectPosMat,

        finalVolumeVasp_ang3,
        density_g_cm3,
        finalForceMat_ev_ang,
        finalStressMat_kbar,
        finalPressure_kbar,
        eigenMat,
        energyNoEntrp,
        energyPerAtom,
        efermi0,
        cbMin,
        vbMax,
        bandgap)
      values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ''',
    ( wrapId,
      smallMap['absPath'],
      smallMap['relPath'],
      json.dumps( smallMap['statMap'],          # statMap in json format
        sort_keys=True, indent=2, separators=(',', ': ')),

      smallMap['icsdNum'],
      smallMap['magType'],
      smallMap['magNum'],
      smallMap['relaxType'],
      smallMap['relaxNum'],

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
      getattr( vaspObj, 'initialCartesianPosMat', None),
      getattr( vaspObj, 'initialDirectPosMat', None),

      getattr( vaspObj, 'finalBasisMat', None),
      getattr( vaspObj, 'finalRecipBasisMat', None),
      getattr( vaspObj, 'finalCartesianPosMat', None),
      getattr( vaspObj, 'finalDirectPosMat', None),

      getattr( vaspObj, 'finalVolumeVasp_ang3', None),
      getattr( vaspObj, 'density_g_cm3', None),
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
  ))
  conn.commit()

#====================================================================


# Recursively format an array, so
#   [[11.1, 22.2], [33.3, 44.4]] )
# becomes the string:
#   array[array[11.1,22.2],array[33.3,44.4]]

def formatArray( vec):
  msg = formatArraySub( vec)
  # print 'formatted array with quotes:\n  %s' % (msg,)
  return msg


#====================================================================


# xxx: special case for None? ... format as NULL?

def formatArraySub( val):
  if isinstance( val, np.ndarray):
    msg = 'array['
    for ii in range(len(val)):
      if ii > 0: msg += ','
      msg += formatArraySub( val[ii])       # recursion
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

def printMap( tag, vmap, maxLen):
  print '\n%s' % (tag,)
  keys = vmap.keys()
  keys.sort()
  for key in keys:
    val = str( vmap[key])
    if len(val) > maxLen: val = val[:maxLen] + '...'
    print '    [%s]: %s' % (key, val,)

#====================================================================




def throwerr( msg):
  print msg
  print >> sys.stderr, msg
  raise Exception( msg)

#====================================================================

if __name__ == '__main__': main()

#====================================================================

