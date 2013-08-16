#!/usr/bin/env python

import datetime, fractions, json, os, re, sys
import psycopg2


#====================================================================


def badparms( msg):
  print '\nError: %s' % (msg,)
  print 'Parms:'
  print '  -bugLev     <int>      debug level'
  print '  -inSpec     <string>   inSpecJsonFile'
  sys.exit(1)


#====================================================================


def main():
  '''
  This program adds additional information to the model database table.
  The following functions in this file fill the indicated columns
  in the model table.  The columns must have been created previously
  by the fillDbVasp.py function createTable.

  ==============  ===========   ==============================================
  Function        Column        Notes
  ==============  ===========   ==============================================
  addChemforms    formula       Standard chemical formula: ``"H2 O"``.

  addChemForms    chemtext      Structured formula, easier for parsing.
                                Every token is surrounded by spaces, and
                                single occurance atoms have the explicit
                                "1" count:
                                ``" H 2 O 1 "``.

  addMinenergy    minenergyid   == mident having min energyperatom
                                for this formula and symgroupnum.
  ==============  ===========   ==============================================


  Command line parameters:

  =============   ===========   ==============================================
  Parameter       Type          Description
  =============   ===========   ==============================================
  **-bugLev**     integer       Debug level.  Normally 0.
  **-inSpec**     string        JSON file containing DB parameters.  See below.
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
  **dbtableicsd**        Database name of the "icsd" table.
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
      "dbtableicsd"    : "icsd"
    }

  '''

  bugLev     = None
  inSpec     = None

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if   key == '-bugLev': bugLev = int( val)
    elif key == '-inSpec': inSpec = val
    else: badparms('unknown key: "%s"' % (key,))

  if bugLev == None: badparms('parm not specified: -bugLev')
  if inSpec == None: badparms('parm not specified: -inSpec')

  augmentDb( bugLev, inSpec)


#====================================================================


def augmentDb( bugLev, inSpec):
  '''
  Adds additional information to the model database table.

  See documentation for the :func:`main` function.

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.
  * inSpec (str): Name of JSON file containing DB parameters.
                  See description at :func:`main`.

  **Returns**

  * None
  '''

  with open( inSpec) as fin:
    specMap = json.load( fin)

  dbhost       = specMap.get('dbhost', None)
  dbport       = specMap.get('dbport', None)
  dbuser       = specMap.get('dbuser', None)
  dbpswd       = specMap.get('dbpswd', None)
  dbname       = specMap.get('dbname', None)
  dbschema     = specMap.get('dbschema', None)
  dbtablemodel = specMap.get('dbtablemodel', None)
  dbtableicsd  = specMap.get('dbtableicsd', None)

  if dbhost == None:       badparms('inSpec name not found: dbhost')
  if dbport == None:       badparms('inSpec name not found: dbport')
  if dbuser == None:       badparms('inSpec name not found: dbuser')
  if dbpswd == None:       badparms('inSpec name not found: dbpswd')
  if dbname == None:       badparms('inSpec name not found: dbname')
  if dbschema == None:     badparms('inSpec name not found: dbschema')
  if dbtablemodel == None: badparms('inSpec name not found: dbtablemodel')
  if dbtableicsd == None:  badparms('inSpec name not found: dbtableicsd')
  dbport = int( dbport)

  queryCols = [
    'model.mident',
    'model.formula',
    'model.energyperatom',
    'model.typenames',
    'model.typenums',
    'icsd.symgroupnum']

  conn = None
  cursor = None
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

    db_rows = dbQuery( bugLev, conn, cursor,
      dbtablemodel, dbtableicsd, queryCols)

    curCols = list( queryCols)       # shallow copy

    newCols = addChemforms( bugLev, curCols, db_rows)   # updates db_rows
    curCols += newCols

    # addMinenergy uses the formula created by addChemforms
    newCols = addMinenergy( bugLev, curCols, db_rows)   # updates db_rows
    curCols += newCols

    newCols = addEnthalpy( bugLev, curCols, db_rows)   # updates db_rows
    curCols += newCols

    dbUpdate(
      bugLev, conn, cursor, dbtablemodel, queryCols, curCols, db_rows)

  finally:
    if cursor != None: cursor.close()
    if conn != None: conn.close()


#====================================================================


def getIcol( names, nm):
  '''
  Returns the index of nm in names.  Calls throwerr if not found.

  **Parameters**:

  * names (str[]): The list of strings.
  * nm (str): The query string.

  **Returns**

  * ix(int): index of nm in names.

  Raises: Exception if nm not in names.
  '''

  if not nm in names: throwerr('unknown column name: %s' % (nm,))
  return names.index( nm)


#====================================================================


# Adds columns: formula, chemtext.
# Example:
#   original = 'H4 O2'
#   formula  = 'H2 O'       # factor out the greatest common divisor
#   chemtext = ' H 2 O 1 '  # every token is surrounded by spaces
#
# Returns newCols.  Updates db_rows.

def addChemforms( bugLev, curCols, db_rows):
  '''
  Calculates the formula and chemtext fields.

  Appends two elements to each row:

  formula:
    chemical formula, determined from typenames and typenums,
    and factoring by the greatest common divison.
    Elements are in alphabetic order.
    For example, ``'H2 O'``.

  chemtext:
    Same as the formula, but every token is surrounded
    spaces and singletons have an explicit '1',
    for ease in parsing.
    For example, ``' H 2 O 1 '``.

  **Parameters**:

  * curCols (str[]): List of column names.
  * db_rows (str[][]): Database rows: [irow][icol].
                         We append two elements to each row.

  **Returns**

  * newCols (str[]): list of new column names == ['formula', 'chemtext']
  '''

  if bugLev >= 1:
    print 'addChemform beg: curCols: %s' % (curCols,)
    print 'addChemform beg: num rows: %d' % (len(db_rows),)
    if len(db_rows) > 0:
      print 'addChemform beg: len of first row: %d' % (len(db_rows[0]),)
      print 'addChemform beg: first row: %s' % (db_rows[0],)

  icolmident = getIcol( curCols, 'model.mident')
  icolnames = getIcol( curCols, 'model.typenames')
  icolnums  = getIcol( curCols, 'model.typenums')

  # Add new columns to each row
  for row in db_rows:
    mident = row[icolmident]
    tnames = row[icolnames]
    tnums = row[icolnums]
    if tnames != None and tnums != None:
      tlen = len( tnames)
      if len( tnums) != tlen: throwerr('tlen mismatch')

      # Replace tnums with tnums / gcd( tnums)
      if tlen == 1: tnums = [1]
      else:
        gcd = tnums[0]
        for jj in range(1,tlen):
          gcd = fractions.gcd( gcd, tnums[jj])
        for jj in range(tlen):
          tnums[jj] /= gcd

      # In readVasp we insure that the typenames and atomnames
      # are in alphabetic order.

      # For chemtext we insert an initial and final blank,
      # so every value is surrounded by spaces,
      # for easier handling in SQL.
      formula = ''
      chemtext = ''
      for ii in range(tlen):
        # Coordinate formula format with pyramid: views.py: vwQueryStd
        if len(formula) > 0: formula += ' '
        formula += tnames[ii]
        if tnums[ii] != 1:
          formula += str(tnums[ii])
        chemtext += ' %s %d' % (tnames[ii], tnums[ii],)
      chemtext += ' '

      if bugLev >= 1:
        print ('addChemform: mident: %d  tnames: %s  tnums: %s'
          + '  formula: %s  chemtext: %s') \
          % (mident, tnames, tnums, repr( formula), repr( chemtext),)
      row.append( formula)
      row.append( chemtext)
    else: row += [None, None]

  newCols = ['formula', 'chemtext']
  if bugLev >= 1:
    print 'addChemform end: newCols: %s' % (newCols,)
  return newCols


#====================================================================


# Returns newCols.  Updates db_rows.
# addMinenergy uses the formula created by addChemforms

def addMinenergy( bugLev, curCols, db_rows):
  '''
  Calculates the min energyperatom for each formula.

  Appends an element to each row:

  minenergyid == the mident of the row having the min energyperatom
  for this formula.

  **Parameters**:

  * curCols (str[]): List of column names.
  * db_rows (str[][]): Database rows: [irow][icol].
                         We append one element to each row.

  **Returns**

  * newCols (str[]): list of new column names == ['minenergyid'].
  '''

  if bugLev >= 1:
    print 'addMinenergy beg: curCols: %s' % (curCols,)
    print 'addMinenergy beg: num rows: %d' % (len(db_rows),)
    if len(db_rows) > 0:
      print 'addMinenergy beg: len of first row: %d' % (len(db_rows[0]),)
      print 'addMinenergy beg: first row: %s' % (db_rows[0],)

  icolMident = getIcol( curCols, 'model.mident')
  icolFormula = getIcol( curCols, 'model.formula')
  icolEnergy = getIcol( curCols, 'model.energyperatom')
  icolSymgroupnum = getIcol( curCols, 'icsd.symgroupnum')

  minMap = {}       # formulaSymnum -> [minEnergy, mident]
  for row in db_rows:
    mident = row[icolMident]
    formula = row[icolFormula]
    energy = row[icolEnergy]
    symgroupnum = row[icolSymgroupnum]

    formulaSymnum = '%s,%s' % (formula, symgroupnum,) # symgroupnum may be None
    pair = minMap.get( formulaSymnum, None)
    if pair == None or energy < pair[0]:
      minMap[formulaSymnum] = [energy, mident]

  # Add new column minenergyid to each row
  for row in db_rows:
    mident = row[icolMident]
    formula = row[icolFormula]
    symgroupnum = row[icolSymgroupnum]
    formulaSymnum = '%s,%s' % (formula, symgroupnum,) # symgroupnum may be None

    pair = minMap[formulaSymnum]      # [minEnergy, minId]
    minId = pair[1]
    if bugLev >= 1:
      print 'addMinenergy: mident: %d  formula: %s  symgrp: %s  minId: %d' \
        % (mident, formula, symgroupnum, minId,)
    row.append( minId)      # mident having the min energy for this formula

  newCols = ['minenergyid']
  if bugLev >= 1:
    print 'addMinenergy end: newCols: %s' % (newCols,)
  return newCols



#====================================================================


# Returns newCols.  Updates db_rows.

def addEnthalpy( bugLev, curCols, db_rows):
  '''
  Calculates the enthalpy of formation per atom.

  Appends an element to each row.

  **Parameters**:

  * curCols (str[]): List of column names.
  * db_rows (str[][]): Database rows: [irow][icol].
                       We append one element to each row.

  **Returns**

  * newCols (str[]): list of new column names == ['enthalpy'].
  '''

  if bugLev >= 1:
    print 'addEnthalpy beg: curCols: %s' % (curCols,)
    print 'addEnthalpy beg: num rows: %d' % (len(db_rows),)
    if len(db_rows) > 0:
      print 'addEnthalpy beg: len of first row: %d' % (len(db_rows[0]),)
      print 'addEnthalpy beg: first row: %s' % (db_rows[0],)

  icolMident = getIcol( curCols, 'model.mident')
  icolFormula = getIcol( curCols, 'model.formula')
  icolEnergy = getIcol( curCols, 'model.energyperatom')
  icolTypenames = getIcol( curCols, 'model.typenames')
  icolTypenums = getIcol( curCols, 'model.typenums')

  # Add new column enthalpy to each row
  for row in db_rows:
    mident = row[icolMident]
    formula = row[icolFormula]
    typenames = row[icolTypenames]
    typenums = row[icolTypenums]
    energy = row[icolEnergy]
    enthalpy = calcEnthalpy( typenames, typenums, energy)  # may be None
    if bugLev >= 1:
      print 'addEnthalpy: mident: %d  formula: %s  energy: %g  enthalpy: %s' \
        % (mident, formula, energy, enthalpy,)
    row.append( enthalpy)

  newCols = ['enthalpy']
  if bugLev >= 1:
    print 'addEnthalpy end: newCols: %s' % (newCols,)
  return newCols


#====================================================================






def calcEnthalpy( typenames, typenums, energy):
  '''
  DOI: 10.1103/PhysRevB.85.115104

  http://prb.aps.org/pdf/PRB/v85/i11/e115104
  Correcting density functional theory for accurate predictions
  of compound enthalpies of formation:
  Fitted elemental-phase reference energies
  Vladan Stevanovic, Stephan Lany, Xiuwen Zhang, Alex Zunger

  page 11, Table V: mu^{FERE}

  Email from Stevanovic, Monday, August 12, 2013 5:45 PM
  For the enthalpy of formation calculations I will use the
  following example. So, if we have a ternary compound with the
  chemical formula A_mB_nX_l, where A, B and X represent the
  symbols of the elements forming the compound and if N=m+n+l the
  total number of atoms in the compound the enthalpy of formation
  can be calculated as:

  dHf (eV/atom) = [Etot(eV/atom) * N - (m*mus_final['A']
    + n*mus_final['B'] + l*mus_final['X'] ) ] / N

  where Etot(eV/atom) is the VASP total energy per atom which is
  currently listed in the database and mus_final['A'],
  mus_final['B'], and mus_final['X'] you read from the attached
  dictionary.
  '''

  mus_final = {
    'Ag': -0.82700958541595615,
    'Al': -3.02,
    'As': -5.06,
    'Au': -2.2303410086960551,
    'Ba': -1.3944992462870172,
    'Be': -3.3972092621754264,
    'Bi': -4.3853003286558812,
    'Ca': -1.64,
    'Cd': -0.56,
    'Cl': -1.6262437135301639,
    'Co': -4.7543486260270402,
    'Cr': -7.2224146752384204,
    'Cu': -1.9725806522979044,
    'F' : -1.7037867766570287,
    'Fe': -6.1521343161090325,
    'Ga': -2.37,
    'Ge': -4.137439286830797,
    'Hf': -7.397695761161847,
    'Hg': -0.12361566177444684,
    'In': -2.31,
    'Ir': -5.964577394407752,
    'K' : -0.80499202755075006,
    'La': -3.6642174822805287,
    'Li': -1.6529591953887741,
    'Mg': -0.99,
    'Mn': -6.9965778258511993,
    'N' : -8.51,
    'Na': -1.0640326227725869,
    'Nb': -6.6867516375690608,
    'Ni': -3.5687859474688026,
    'O' : -4.76,
    'P' : -5.64,
    'Pd': -3.1174044624888873,
    'Pt': -3.9527597082085424,
    'Rb': -0.6750560483522855,
    'Rh': -4.7622899695820369,
    'S' : -4.00,
    'Sb': -4.2862260747305099,
    'Sc': -4.6302422200922519,
    'Se': -3.55,
    'Si': -4.9927748122726356,
    'Sn': -3.7894939351245469,
    'Sr': -1.1674559193419329,
    'Ta': -8.8184831379805324,
    'Te': -3.2503408197224912,
    'Ti': -5.5167842601434147,
    'V' : -6.4219725884764864,
    'Y' : -4.812621315561298,
    'Zn': -0.84,
    'Zr': -5.8747056261113126,
  }

  totNum = sum( typenums)

  enthalpy = energy

  for ii in range(len(typenames)):
    name = typenames[ii]
    num = typenums[ii]
    mufere = mus_final.get( name, None)
    if mufere == None: enthalpy = None
    if enthalpy != None:
      enthalpy -= num * mufere / float(totNum)

  return enthalpy


#====================================================================


def dbQuery( bugLev, conn, cursor, dbtablemodel, dbtableicsd, queryCols):
  '''
  Issues a DB SQL query and returns the results.

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.
  * conn (psycopg2.connection): Open DB connection
  * cursor (psycopg2.cursor): Open DB cursor
  * dbtablemodel (str): Database name of the "model" table.
  * dbtableicsd (str): Database name of the "icsd" table.
  * queryCols (str[]): List of column names to be retrieved.

  **Returns**

  * db_rows(str[][]): Database rows: [irow][icol].
  '''

  if queryCols[0] != 'model.mident': throwerr('first col must be mident')
  db_rows = None

  nmStg = ', '.join( queryCols)
  sqlMsg = 'SELECT %s FROM %s LEFT OUTER JOIN %s ON (model.icsdnum = icsd.icsdnum) ORDER BY mident' \
    % (nmStg, dbtablemodel, dbtableicsd)

  cursor.execute( sqlMsg)
  db_rows = cursor.fetchall()
  db_cols = [desc[0] for desc in cursor.description]

  if len( queryCols) != len( db_cols):
    throwerr('db_cols mismatch: query: %s  db: %s' \
      % (queryCols, db_cols,))

  # Convert rows from tuples to lists so we can modify them later
  for irow in range(len(db_rows)):
    db_rows[irow] = list( db_rows[irow])

  if bugLev >= 1:
    print 'dbQuery end: queryCols: %s' % (queryCols,)
    print 'dbQuery end: len( db_rows): %d' % (len( db_rows))
  return db_rows





#====================================================================

# On entry curCols is the same as queryCols but has some appended columns.
# The rows match curCols.
# Write the appended values for each row to the db.

def dbUpdate(
  bugLev, conn, cursor, dbtablemodel, queryCols, curCols, db_rows):
  '''
  Issues a DB SQL update.

  Updates every row for just the newly added columns,
  which are curCols - queryCols.

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.
  * conn (psycopg2.connection): Open DB connection
  * cursor (psycopg2.cursor): Open DB cursor
  * dbtablemodel (str): Database name of the "model" table.
  * queryCols (str[]): List of original column names.
  * curCols (str[]): List of current column names == queryCols + new cols.
  * db_rows(str[][]): Database rows: [irow][icol].

  **Returns**

  * None
  '''

  if bugLev >= 1:
    print 'dbUpdate beg: queryCols: %s' % (queryCols,)
    print 'dbUpdate beg: curCols:   %s' % (curCols,)
    print 'dbUpdate beg: len( db_rows): %d' % (len( db_rows))
  qlen = len( queryCols)
  updLen = len( curCols) - qlen
  icolmid = getIcol( curCols, 'model.mident')
  if icolmid != 0: throwerr('first col must be mident')
  if curCols[:qlen] != queryCols: throwerr('curCols mismatch')

  newCols = curCols[qlen:]
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
  if bugLev >= 1: print 'dbUpdate: update done'

  conn.commit()
  if bugLev >= 1: print 'dbUpdate: commit done'


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
