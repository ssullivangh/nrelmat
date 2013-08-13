#!/usr/bin/env python

import datetime, json, os, re, sys
import psycopg2

import readVasp


#====================================================================


def badparms( msg):
  print '\nError: %s' % (msg,)
  print '  See usage info.'
  sys.exit(1)


#====================================================================


def main():
  '''
  This program generates statistics from the icsdcif database table.
  It only reads the database; it does not alter it.

  Command line parameters:

  =============   ===========   ==============================================
  Parameter       Type          Description
  =============   ===========   ==============================================
  **-bugLev**     integer       Debug level.  Normally 0.
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

  bugLev     = None
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
    if   key == '-bugLev': bugLev = int( val)
    elif key == '-loLim': loLim = int( val)
    elif key == '-hiLim': hiLim = int( val)
    elif key == '-incr': incr = int( val)
    elif key == '-inSpec': inSpec = val
    elif key == '-outData': outData = val
    else: badparms('unknown key: "%s"' % (key,))

  if bugLev == None: badparms('parm not specified: -bugLev')
  if loLim == None: badparms('parm not specified: -loLim')
  if hiLim == None: badparms('parm not specified: -hiLim')
  if incr == None: badparms('parm not specified: -incr')
  if inSpec == None: badparms('parm not specified: -inSpec')
  if outData == None: badparms('parm not specified: -outData')

  tuples = statsMain( bugLev, loLim, hiLim, incr, inSpec)

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


def statsMain( bugLev, loLim, hiLim, incr, inSpec):
  '''
  Opens the database and calls function :func:`statsA`.

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.
  * loLim (int): The overall low limit for statsA.
  * hiLim (int): The overall high limit for statsA.
  * incr (int): The section length = increment for the sections for statsA.
  * inSpec (str): Name of JSON file containing DB parameters.
                  See description at :func:`main`.

  **Returns**:

  * tuples from :func:`statsA`.
  '''


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
    if bugLev >= 1:
      print 'main: got conn.  dbhost: %s  dbport: %d' % (dbhost, dbport,)
    cursor = conn.cursor()
    cursor.execute('set search_path to %s', (dbschema,))
    
    tuples = statsA( bugLev, loLim, hiLim, incr, cursor)

  finally:
    if cursor != None: cursor.close()
    if conn != None: conn.close()

  return tuples


#====================================================================



def statsA( bugLev, loLim, hiLim, incr, cursor):
  '''
  Chops the region from loLim to hiLim into sections of
  length incr, and for each section
  finds the number of rows in the icsdcif table having
  numcellatom within the section bounds.

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.
  * loLim (int): The overall low limit.
  * hiLim (int): The overall high limit.
  * incr (int): The section length = increment for the sections.
  * cursor (psycopg2.cursor): Open DB cursor

  **Returns**:

  * tuples: list of pairs: [lowBnd, numCases]
    where tuples[k] has
    loBnd = loLim + k*incr
    and numCases = num rows having loBnd <= numcellatom < loBnd+incr.
  '''

  tuples = []
  for nn in range( loLim, hiLim, incr):

    cursor.execute('SELECT count(*) FROM icsdcif'
      + ' WHERE numcellatom >= %s AND numcellatom < %s'
      + ' and formuladelta < 0.01'
      + ' and occudelta < 0.01'
      + ' and \'H\' != all( formulanames)',
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
