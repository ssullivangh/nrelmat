#!/usr/bin/env python

import datetime, json, os, re, sys, traceback, cPickle
import numpy as np
import psycopg2

import readVasp


buglev = 0  # xxx make a parm

#====================================================================


def badparms( msg):
  print '\nError: %s' % (msg,)
  print 'Parms:'
  print '  -buglev     <int>      debug level'
  print '  -func       <string>   createTableModel / fillTable'
  print '  -inDigest   <string>   input digest file, created by'
  print '                           digestVasp_a.py.'
  print '  -wrapId     <string>'
  print '  -inSpec     <string>   inSpecJsonFile'
  sys.exit(1)


#====================================================================


def main():
  '''
  Read a digest file created by digestVasp.py and add
  rows to the database table "model".
  The function is determined by the **-func** parameter; see below.

  This function is called by wrapReceive.py.

  Command line parameters:

  ==============   =========    ==============================================
  Parameter        Type         Description
  ==============   =========    ==============================================
  **-buglev**      integer      Debug level.  Normally 0.
  **-func**        string       Function.  See below.
  **-inDigest**    string       Input digest file.
  **-wrapId**      string       The unique id of this upload, created
                                by wrapReceive.py from the uploaded file name.
  **-inSpec**      string       JSON file containing parameters.  See below.
  ==============   =========    ==============================================

  **Values for the -func Parameter:**

  **createTableModel**
    Drop and create the model table.  In this case the -inDigest
    and -wrapId parameters should be "none".

  **fillTable**
    Read the digest file and insert database table rows.

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
  ===================    ==============================================

  **inSpec file example:**::

    {
      "dbhost"         : "scctest",
      "dbport"         : "6432",
      "dbuser"         : "x",
      "dbpswd"         : "x",
      "dbname"         : "cidlada",
      "dbschema"       : "satom",
      "dbtablemodel"   : "model"
    }

  '''

  buglev     = None
  func       = None
  inDigest   = None
  wrapId     = None
  inSpec = None

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if   key == '-buglev': buglev = int( val)
    elif key == '-func': func = val
    elif key == '-inDigest': inDigest = val
    elif key == '-wrapId': wrapId = val
    elif key == '-inSpec': inSpec = val
    else: badparms('unknown key: "%s"' % (key,))

  if buglev == None: badparms('parm not specified: -buglev')
  if func == None: badparms('parm not specified: -func')
  if inDigest == None: badparms('parm not specified: -inDigest')
  if wrapId == None: badparms('parm not specified: -wrapId')
  if inSpec == None: badparms('parm not specified: -inSpec')

  fillDbVasp( buglev, func, inDigest, wrapId, inSpec)


#====================================================================



def fillDbVasp(
  buglev,
  func,
  inDigest,
  wrapId,
  inSpec):

  with open( inSpec) as fin:
    specMap = json.load( fin)

  dbhost   = specMap.get('dbhost', None)
  dbport   = specMap.get('dbport', None)
  dbuser   = specMap.get('dbuser', None)
  dbpswd   = specMap.get('dbpswd', None)
  dbname   = specMap.get('dbname', None)
  dbschema = specMap.get('dbschema', None)
  dbtablemodel   = specMap.get('dbtablemodel', None)

  if dbhost == None:   badparms('inSpec name not found: dbhost')
  if dbport == None:   badparms('inSpec name not found: dbport')
  if dbuser == None:   badparms('inSpec name not found: dbuser')
  if dbpswd == None:   badparms('inSpec name not found: dbpswd')
  if dbname == None:   badparms('inSpec name not found: dbname')
  if dbschema == None: badparms('inSpec name not found: dbschema')
  if dbtablemodel   == None: badparms('inSpec name not found: dbtablemodel')
  dbport = int( dbport)


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
      createTableModel( buglev, conn, cursor, dbtablemodel)
    elif func == 'fillTable':
      fillTable( buglev, inDigest, conn, cursor, wrapId, dbtablemodel)
    else: throwerr('unknown func: "%s"' % (func,))
  finally:
    if cursor != None: cursor.close()
    if conn != None: conn.close()


#====================================================================


def createTableModel(
  buglev,
  conn,
  cursor,
  dbtablemodel):

  cursor.execute('drop table if exists %s' % (dbtablemodel,))
  conn.commit()

  cursor.execute('''
    CREATE TABLE %s (
      mident         serial,
      wrapid         text,
      path           text,

      icsdNum        int,   -- ICSD number in CIF file: _database_code_ICSD

      magType        text,  -- type of magnetic moment:
                            --   hsf:  hs-ferro.  magNum = 0.
                            --   hsaf: hs-anti-ferro.  magNum = test num.
                            --   lsf:  ls-ferro.  magNum = 0.
                            --   lsaf: ls-anti-ferro.  magNum = test num.
                            --   nm:   non-magnetic.  magNum = 0.
      magNum         int,   -- number of hs-anti-ferro or ls-anti-ferro test.

      relaxType      text,  -- Type of run:
                            --   std: standard,
                            --   rc:  relax_cellshape,
                            --   ri:  relax_ions
      relaxNum       int,   -- Folder num for rc or ri: 0, 1, ...

      excMsg         text,  -- exception msg from digestVasp.py
      excTrace       text,  -- exception trace from digestVasp.py
                            -- If excMsg != None,
                            -- all following fields are None.

      --- program, version, date etc ---
      runDate        timestamp,          -- 2013-03-11 10:07:01
      iterTotalTime  double precision,
      --- incar parameters ---
      systemName     text,               -- mos2_024000.cif
      encut          double precision,   -- 252.
      ibrion         int,
      isif           int,
      --- kpoints ---
      --- general parameters ---
      --- atom info ---
      numAtom        int,                -- == sum( typeNums)
      typeNames      text[],             -- ['Mo' 'S']
      typeNums       int[],              -- [2 4]
      typeMasses     float[],
      typePseudos    text[],
      typeValences   int[],
      atomNames      text[],
      atomMasses     float[],
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
      finalVolumeVasp         double precision,
      density                 double precision,

      --- last calc forces ---
      finalForceMat           double precision[][],
      finalStressMat          double precision[][],
      finalPressure           double precision,

      --- eigenvalues and occupancies ---
      eigenMat                double precision[][],

      --- energy, efermi0 ---
      finalEnergy    double precision,   -- -13.9
      energyPerAtom  double precision,   -- -13.9
      efermi0        double precision,   -- 5.93
      --- cbMin, vbMax, bandgap ---
      cbMin          double precision,   -- 7.199
      vbMax          double precision,   -- 5.8574
      bandgap        double precision,   -- 1.3416

      --- misc ---
      fileNames      text[],
      fileSizes      text[],

      --- columns filled by augmentDb.py ---
      isminenergy    boolean,
      chemsum        text,              -- 'H2 O'
      chemform       text               -- ' H 2 O '
                                        -- every token surrounded by spaces
    )
  ''' % (dbtablemodel,))
  conn.commit()
  print 'fillDbVasp: table created'

  cursor.execute('''
    CREATE INDEX %s_mident_index ON %s (mident)
  ''' % (dbtablemodel, dbtablemodel,))
  conn.commit()
  print 'fillDbVasp: index created'



#====================================================================


def fillTable(
  buglev,
  inDigest,
  conn,
  cursor,
  wrapId,
  dbtablemodel):

  if not os.path.isfile(inDigest):
    throwerr('inDigest is not a file: "%s"' % (inDigest,))

  with open( inDigest) as fin:
    resList = cPickle.load( fin)

  for resObj in resList:
    print 'fillDbTable: adding realPath: %s ...' \
      % (getattr( resObj, 'realPath', None),),

    typeNums = getattr( resObj, 'typeNums', None)
    numAtom = None
    if typeNums != None: numAtom = sum( typeNums)

    finalEnergyWithout = getattr( resObj, 'finalEnergyWithout', None)
    energyPerAtom = None
    if numAtom != None and finalEnergyWithout != None:
      energyPerAtom = finalEnergyWithout / numAtom

    cursor.execute(
      '''
        insert into
      '''
      + dbtablemodel + 
      ''' (
          wrapid, path, icsdNum, magType, magNum,
          relaxType, relaxNum,
          excMsg, excTrace,
          runDate, iterTotalTime,
          systemName, encut, ibrion, isif,
          numAtom, typeNames, typeNums, typeMasses, typePseudos, typeValences,
          atomNames, atomMasses, atomPseudos, atomValences,

          initialBasisMat,
          initialRecipBasisMat,
          initialCartesianPosMat,
          initialDirectPosMat,

          finalBasisMat,
          finalRecipBasisMat,
          finalCartesianPosMat,
          finalDirectPosMat,

          finalVolumeVasp,
          density,
          finalForceMat,
          finalStressMat,
          finalPressure,
          eigenMat,
          finalEnergy,
          energyPerAtom,
          efermi0,
          cbMin, vbMax, bandgap,
          fileNames, fileSizes)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
      ''',
      ( wrapId,
        getattr( resObj, 'realPath', None),
        getattr( resObj, 'icsdNum', None),
        getattr( resObj, 'magType', None),
        getattr( resObj, 'magNum', None),
        getattr( resObj, 'relaxType', None),
        getattr( resObj, 'relaxNum', None),
        getattr( resObj, 'excMsg', None),
        getattr( resObj, 'excTrace', None),
        getattr( resObj, 'runDate', None),
        getattr( resObj, 'iterTotalTime', None),
        getattr( resObj, 'systemName', None),
        getattr( resObj, 'encut', None),
        getattr( resObj, 'ibrion', None),
        getattr( resObj, 'isif', None),
        numAtom,
        getattr( resObj, 'typeNames', None),
        getattr( resObj, 'typeNums', None),
        getattr( resObj, 'typeMasses', None),
        getattr( resObj, 'typePseudos', None),
        getattr( resObj, 'typeValences', None),
        getattr( resObj, 'atomNames', None),
        getattr( resObj, 'atomMasses', None),
        getattr( resObj, 'atomPseudos', None),
        getattr( resObj, 'atomValences', None),

        getattr( resObj, 'initialBasisMat', None),
        getattr( resObj, 'initialRecipBasisMat', None),
        getattr( resObj, 'initialCartesianPosMat', None),
        getattr( resObj, 'initialDirectPosMat', None),

        getattr( resObj, 'finalBasisMat', None),
        getattr( resObj, 'finalRecipBasisMat', None),
        getattr( resObj, 'finalCartesianPosMat', None),
        getattr( resObj, 'finalDirectPosMat', None),

        getattr( resObj, 'finalVolumeVasp', None),
        getattr( resObj, 'density', None),
        getattr( resObj, 'finalForceMat', None),
        getattr( resObj, 'finalStressMat', None),
        getattr( resObj, 'finalPressure', None),
        getattr( resObj, 'eigenMat', None),
        getattr( resObj, 'finalEnergyWithout', None),
        energyPerAtom,
        getattr( resObj, 'efermi0', None),
        getattr( resObj, 'cbMin', None),
        getattr( resObj, 'vbMax', None),
        getattr( resObj, 'bandgap', None),
        getattr( resObj, 'fileNames', None),
        getattr( resObj, 'fileSizes', None),
      ))
    conn.commit()
    print ' done'

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

def throwerr( msg):
  print msg
  print >> sys.stderr, msg
  raise Exception( msg)

#====================================================================

if __name__ == '__main__': main()

#====================================================================

