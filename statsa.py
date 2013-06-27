#!/usr/bin/env python

import datetime, json, os, re, sys, traceback, cPickle
import numpy as np
import psycopg2

import readVasp


buglev = 0  # xxx make a parm

#====================================================================


def badparms( msg):
  print '\nError: %s' % (msg,)
  print '  See usage info.'
  sys.exit(1)


#====================================================================


def main():
  '''
  This program generates statistics on the icsd database.
  It only reads the database; it does not alter the database.

  Command line parameters:

  =============   ===========   ==============================================
  Parameter       Type          Description
  =============   ===========   ==============================================
  **-buglev**     integer       Debug level.  Normally 0.
  **-loLim**      integer       Low limit for numcellatom.
  **-hiLim**      integer       High limit for numcellatom.
  **-incr**       integer       Increment for numcellatom.
  **-inSpec**     string        JSON file containing parameters.  See below.
  **-outData**    string        output file for plot data
  =============   ===========   ==============================================

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
  loLim      = None
  hiLim      = None
  incr       = None
  inSpec     = None
  outData    = None

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if   key == '-buglev': buglev = int( val)
    elif key == '-loLim': loLim = int( val)
    elif key == '-hiLim': hiLim = int( val)
    elif key == '-incr': incr = int( val)
    elif key == '-inSpec': inSpec = val
    elif key == '-outData': outData = val
    else: badparms('unknown key: "%s"' % (key,))

  if buglev == None: badparms('parm not specified: -buglev')
  if loLim == None: badparms('parm not specified: -loLim')
  if hiLim == None: badparms('parm not specified: -hiLim')
  if incr == None: badparms('parm not specified: -incr')
  if inSpec == None: badparms('parm not specified: -inSpec')
  if outData == None: badparms('parm not specified: -outData')

  tuples = statsMain( buglev, loLim, hiLim, incr, inSpec)

  with open( outData, 'w') as fout:
    totalNumCase = 0;
    totalTimeHour = 0;
    for tup in tuples:
      ncell = tup[0]
      ncase = tup[1]
      totalNumCase += ncase
      indivTimeSec = 12 * (ncell + 0.5 * incr) ** 2
      totalTimeHour += ncase * indivTimeSec / 3600.
      print >> fout, '%g  %g  %g  %g' \
        % (ncell, ncase, totalNumCase, totalTimeHour,)


#====================================================================


def statsMain( buglev, loLim, hiLim, incr, inSpec):

  with open( inSpec) as fin:
    specMap = json.load( fin)

  dbhost   = specMap.get('dbhost', None)
  dbport   = specMap.get('dbport', None)
  dbuser   = specMap.get('dbuser', None)
  dbpswd   = specMap.get('dbpswd', None)
  dbname   = specMap.get('dbname', None)
  dbschema = specMap.get('dbschema', None)
  dbtablemodel  = specMap.get('dbtablemodel', None)

  if dbhost == None:   badparms('inSpec name not found: dbhost')
  if dbport == None:   badparms('inSpec name not found: dbport')
  if dbuser == None:   badparms('inSpec name not found: dbuser')
  if dbpswd == None:   badparms('inSpec name not found: dbpswd')
  if dbname == None:   badparms('inSpec name not found: dbname')
  if dbschema == None: badparms('inSpec name not found: dbschema')
  if dbtablemodel == None:  badparms('inSpec name not found: dbtablemodel')
  dbport = int( dbport)

  conn = None
  cursor = None
  tuples = None
  try:
    conn = psycopg2.connect(
      host=dbhost,
      port=dbport,
      user=dbuser,
      password=dbpswd,
      database=dbname)
    if buglev >= 1:
      print 'main: got conn.  dbhost: %s  dbport: %d' % (dbhost, dbport,)
    cursor = conn.cursor()
    cursor.execute('set search_path to %s', (dbschema,))
    
    tuples = statsA( buglev, loLim, hiLim, incr, cursor)

  finally:
    if cursor != None: cursor.close()
    if conn != None: conn.close()

  return tuples


#====================================================================



def statsA( buglev, loLim, hiLim, incr, cursor):
  tuples = []
  for nn in range( loLim, hiLim, incr):
    db_rows = None

    cursor.execute('SELECT count(*) FROM icsdcif'
      + ' WHERE numcellatom >= %s AND numcellatom < %s'
      + ' and formuladelta < 0.01'
      + ' and occudelta < 0.01'
      + ' and \'H\'  != all( formulanames)',
      (nn, nn + incr,))
    msg = cursor.statusmessage
    # print 'statsA: nn: %d  msg: %s' % (nn, msg,)
    if msg != 'SELECT': throwerr('bad statusmessage')

    rows = cursor.fetchall()
    nval = rows[0][0]
    tuple = [nn, nval]
    print 'statsA: tuple: %s' % (tuple,)
    tuples.append( tuple)

  return tuples

#====================================================================

def throwerr( msg):
  print msg
  print >> sys.stderr, msg
  raise Exception( msg)

#====================================================================


if __name__ == '__main__': main()
