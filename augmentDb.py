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
  print '  -inSpec     <string>   inSpecJsonFile'
  sys.exit(1)


#====================================================================


def main():
  '''
  This program adds additional information to the model database table.
  The following functions in this file fill the indicated columns
  in the model table.  The columns must have been created previously
  by fillDbVasp.py (which is called by wrapReceive.py).

  ==============  ===========   ==============================================
  Function        Column        Notes
  ==============  ===========   ==============================================
  addIsminenergy  isminenergy   == true iff finalenergy == min for this ICSD.
  addChemforms    chemsum       Standard chemical formula, ``"H2 O"``.
  addChemForms    chemform      Structured formula, easier for parsing.
                                Every token is surrounded by spaces:
                                ``" H 2 O 1 "``.
  ==============  ===========   ==============================================


  Command line parameters:

  =============   =========    ==============================================
  Parameter       Type         Description
  =============   =========    ==============================================
  **-buglev**     integer      Debug level.  Normally 0.
  **-inSpec**     string       JSON file containing parameters.  See below.
  =============   =========    ==============================================

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
  inSpec     = None

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if   key == '-buglev': buglev = int( val)
    elif key == '-inSpec': inSpec = val
    else: badparms('unknown key: "%s"' % (key,))

  if buglev == None: badparms('parm not specified: -buglev')
  if inSpec == None: badparms('parm not specified: -inSpec')

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

  queryCols = ['mident', 'icsdnum', 'finalenergy', 'typenames', 'typenums']

  db_rows = dbQuery( buglev, dbhost, dbport, dbuser, dbpswd,
    dbname, dbschema, dbtablemodel, queryCols)

  curCols = list( queryCols)       # shallow copy

  newCols = addIsminenergy( buglev, curCols, db_rows)   # updates db_rows
  curCols += newCols

  newCols = addChemforms( buglev, curCols, db_rows)   # updates db_rows
  curCols += newCols

  dbUpdate( buglev, dbhost, dbport, dbuser, dbpswd,
    dbname, dbschema, dbtablemodel, queryCols, curCols, db_rows)


#====================================================================

def getIcol( names, nm):
  if not nm in names: throwerr('unknown column name: %s' % (nm,))
  return names.index( nm)

#====================================================================

# Returns newCols.  Updates db_rows.

def addIsminenergy( buglev, curCols, db_rows):
  if buglev >= 1:
    print 'addIsminenergy beg: curCols: %s' % (curCols,)
    print 'addIsminenergy beg: first row: %s' % (db_rows[0],)
  icolicsd   = getIcol( curCols, 'icsdnum')
  icolenergy = getIcol( curCols, 'finalenergy')

  icsdMap = {}       # icsdnum -> min finalenergy
  for row in db_rows:
    icsdnum = row[icolicsd]
    energy = row[icolenergy]
    if icsdMap.has_key( icsdnum):
      icsdMap[icsdnum] = min( icsdMap[icsdnum], energy)
    else: icsdMap[icsdnum] = energy

  # Add new column to each row
  for row in db_rows:
    icsdnum = row[icolicsd]
    energy = row[icolenergy]
    if energy == icsdMap[icsdnum]: row.append( True)
    else: row.append( False)

  newCols = ['isminenergy']
  if buglev >= 1:
    print 'addIsminenergy end: newCols: %s' % (newCols,)
    print 'addIsminenergy end: first row: %s' % (db_rows[0],)
  return newCols



#====================================================================

# Adds columns: chemsum, chemform.
# Example:
#   chemsum = 'H2 O'
#   chemform = ' H 2 O 1 '  # every token is surrounded by spaces
#
# Returns newCols.  Updates db_rows.

def addChemforms( buglev, curCols, db_rows):
  if buglev >= 1:
    print 'addChemform beg: curCols: %s' % (curCols,)
    print 'addChemform beg: first row: %s' % (db_rows[0],)
  icolmident = getIcol( curCols, 'mident')
  icolnames = getIcol( curCols, 'typenames')
  icolnums  = getIcol( curCols, 'typenums')

  # Add new columns to each row
  for row in db_rows:
    mident = row[icolmident]
    tnames = row[icolnames]
    tnums = row[icolnums]
    if tnames != None and tnums != None:
      tlen = len( tnames)
      if len( tnums) != tlen: throwerr('tlen mismatch')

      # Sort parallel arrays typenames, typenums by alphabetic order
      ixs = range( tlen)
      def sortFunc( ia, ib):
        return cmp( tnames[ia], tnames[ib])
      ixs.sort( sortFunc)

      # Have initial and final blank so every value is surrounded
      # by spaces, for easier handling in SQL.
      chemsum = ''
      chemform = ''
      for ii in range(tlen):
        if len(chemsum) > 0: chemsum += ' '
        chemsum += tnames[ixs[ii]]
        if tnums[ixs[ii]] != 1:
          chemsum += str(tnums[ixs[ii]])
        chemform += ' %s %d' % (tnames[ixs[ii]], tnums[ixs[ii]],)
      chemform += ' '

      if buglev >= 1:
        print 'addChemform: mident: %d  tnames: %s  tnums: %s  chemsum: %s  chemform: %s' \
          % (mident, tnames, tnums, repr( chemsum), repr( chemform),)
      row.append( chemsum)
      row.append( chemform)
    else: row += [None, None]

  newCols = ['chemsum', 'chemform']
  if buglev >= 1:
    print 'addChemform end: newCols: %s' % (newCols,)
    print 'addChemform end: first row: %s' % (db_rows[0],)
  return newCols


#====================================================================

def dbQuery(
  buglev,
  dbhost,
  dbport,
  dbuser,
  dbpswd,
  dbname,
  dbschema,
  dbtablemodel,
  queryCols):

  if queryCols[0] != 'mident': throwerr('first col must be mident')
  db_rows = None
  conn = None
  cursor = None
  try:
    conn = psycopg2.connect(
      host=dbhost,
      port=dbport,
      user=dbuser,
      password=dbpswd,
      database=dbname)
    if buglev >= 1:
      print 'dbQuery: got conn.  dbhost: %s  dbport: %d' % (dbhost, dbport,)
    cursor = conn.cursor()
    cursor.execute('set search_path to %s', (dbschema,))

    nmstg = ', '.join( queryCols)
    cursor.execute('SELECT %s FROM %s order by icsdnum, mident' \
      % (nmstg, dbtablemodel,))
    db_rows = cursor.fetchall()
    db_cols = [desc[0] for desc in cursor.description]
  finally:
    if cursor != None: cursor.close()
    if conn != None: conn.close()
  if db_cols != queryCols: throwerr('db_cols mismatch')

  # Convert rows from tuples to lists so we can modify them later
  for irow in range(len(db_rows)):
    db_rows[irow] = list( db_rows[irow])

  if buglev >= 1:
    print 'dbQuery end: queryCols: %s' % (queryCols,)
    print 'dbQuery end: len( db_rows): %d' % (len( db_rows))
  return db_rows





#====================================================================

# On entry curCols is the same as queryCols but has some appended columns.
# The rows match curCols.
# Write the appended values for each row to the db.

def dbUpdate(
  buglev,
  dbhost,
  dbport,
  dbuser,
  dbpswd,
  dbname,
  dbschema,
  dbtablemodel,
  queryCols,
  curCols,
  db_rows):

  if buglev >= 1:
    print 'dbUpdate beg: queryCols: %s' % (queryCols,)
    print 'dbUpdate beg: curCols:   %s' % (curCols,)
    print 'dbUpdate beg: len( db_rows): %d' % (len( db_rows))
  qlen = len( queryCols)
  updLen = len( curCols) - qlen
  icolmid = getIcol( curCols, 'mident')
  if icolmid != 0: throwerr('first col must be mident')
  if curCols[:qlen] != queryCols: throwerr('curCols mismatch')
  newCols = curCols[qlen:]

  conn = None
  cursor = None
  try:
    conn = psycopg2.connect(
      host=dbhost,
      port=dbport,
      user=dbuser,
      password=dbpswd,
      database=dbname)
    if buglev >= 1:
      print 'dbUpdate: got conn.  dbhost: %s  dbport: %d  autocommit: %s' \
        % (dbhost, dbport, conn.autocommit,)
    cursor = conn.cursor()
    cursor.execute('set search_path to %s', (dbschema,))

    colStg = ', '.join( newCols)
    for row in db_rows:
      if len(row) != qlen + updLen: throwerr('wrong row len')
      mident = row[icolmid]

      # Convert the values to strings suitable for Postgresql
      updStgs = updLen * [None]
      for ii in range( updLen):
        val = row[qlen+ii]
        if val == None: msg = 'NULL'
        elif isinstance( val, int) \
          or isinstance( val, float) \
          or isinstance( val, bool):
          msg = str( val)
        elif isinstance( val, str):
          msg = '%s' % ( val,)
          msg = msg.replace('\\', '\\\\')     # replace \ with \\
          msg = msg.replace('"',  '\\"')      # replace " with \"
          msg = msg.replace('\'', '\\\'')     # replace ' with \'
          msg = 'E\'' + msg + '\''            # use escaped strings
        else: throwerr('unknown type.  val: %s  type: %s' \
          % (repr(val), type(val),))
        updStgs[ii] = msg

      updStg = ', '.join( updStgs)
      cursor.execute('UPDATE %s SET (%s) = (%s) WHERE mident = %s' \
        % ( dbtablemodel, colStg, updStg, mident,))
    if buglev >= 1: print 'dbUpdate: update done'

    conn.commit()
    if buglev >= 1: print 'dbUpdate: commit done'
  finally:
    if cursor != None: cursor.close()
    if conn != None: conn.close()


#====================================================================

def throwerr( msg):
  print msg
  print >> sys.stderr, msg
  raise Exception( msg)

#====================================================================


if __name__ == '__main__': main()
