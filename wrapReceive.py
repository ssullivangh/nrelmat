#!/usr/bin/env python

import datetime, json, math, os, re
import shutil, subprocess, sys, time, traceback
import psutil
import psycopg2
import fillDbVasp
import augmentDb



#====================================================================


def badparms( msg):
  print '\nError: %s' % (msg,)
  print 'Parms:'
  print ''
  print '  -buglev     <int>      debug level'
  print '  -func       <string>   createTableContrib / readIncoming / redoArch'
  print '  -inSpec     <string>   inSpecJsonFile'
  sys.exit(1)


#====================================================================



def main():
  '''
  This is the receiver for model data uploaded by wrapUpload.sh.
  It updates the model and contrib tables.
  The function is determined by the **-func** parameter; see below.

  This function calls fillDbVasp.py and augmentDb.py.

  Command line parameters:

  =============   =========    ==============================================
  Parameter       Type         Description
  =============   =========    ==============================================
  **-buglev**     integer      Debug level.  Normally 0.
  **-func**       string       Function.  See below.
  **-inSpec**     string       JSON file containing parameters.  See below.
  =============   =========    ==============================================

  **Values for the -func Parameter:**

  **createTableContrib**
    Drop and recreate the contrib table.

  **readIncoming**
    Monitor the inDir for new additions.
    When one is found, move it to archDir, untar it,
    and run fillDbVasp.py on the digest.pkl file
    to insert the results into the model table.
    Also insert a row into the contrib table for this wrapId.

  **redoArch**
    Re-process all the subDirs found in archDir.
    This is useful when someone changes the database tables, for example
    by adding an new column.  Then one can use
    fillDbTable.py:createTableModel,
    and our createTableContrib and redoArch
    to recreate the tables with the new column.

  **inSpec File Parameters:**

  ===================    ==============================================
  Parameter              Description
  ===================    ==============================================
  **inDir**              Input dir for uploaded files.
  **archDir**            Dir used for work and archiving.
  **logFile**            Log file name.
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
      "inDir"          : "/home/scpuser/incoming",
      "archDir"        : "/home/ciduser/arch",
      "logFile"        : "wrapReceive.log",
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

  buglev = None
  func = None
  inSpec = None

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if key == '-buglev': buglev = int( val)
    elif key == '-func': func = val
    elif key == '-inSpec': inSpec = val
    else: badparms('unknown key: "%s"' % (key,))

  if buglev == None: badparms('parm not specified: -buglev')
  if func == None: badparms('parm not specified: -func')
  if inSpec == None: badparms('parm not specified: -inSpec')

  with open( inSpec) as fin:
    specMap = json.load( fin)

  inDir    = specMap.get('inDir', None)
  archDir  = specMap.get('archDir', None)
  logFile  = specMap.get('logFile', None)
  dbhost   = specMap.get('dbhost', None)
  dbport   = specMap.get('dbport', None)
  dbuser   = specMap.get('dbuser', None)
  dbpswd   = specMap.get('dbpswd', None)
  dbname   = specMap.get('dbname', None)
  dbschema = specMap.get('dbschema', None)
  dbtablecontrib = specMap.get('dbtablecontrib', None)
  dbtablemodel   = specMap.get('dbtablemodel', None)

  if inDir == None:    badparms('inSpec name not found: inDir')
  if archDir == None:  badparms('inSpec name not found: archDir')
  if logFile == None:  badparms('inSpec name not found: logFile')
  if dbhost == None:   badparms('inSpec name not found: dbhost')
  if dbport == None:   badparms('inSpec name not found: dbport')
  if dbuser == None:   badparms('inSpec name not found: dbuser')
  if dbpswd == None:   badparms('inSpec name not found: dbpswd')
  if dbname == None:   badparms('inSpec name not found: dbname')
  if dbschema == None: badparms('inSpec name not found: dbschema')
  if dbtablecontrib == None: badparms('inSpec name not found: dbtablecontrib')
  if dbtablemodel   == None: badparms('inSpec name not found: dbtablemodel')
  dbport = int( dbport)


  # Quit if there's a duplicate process already running.
  checkDupProcs()

  inDirPath = os.path.abspath( inDir)
  archDirPath = os.path.abspath( archDir)
  logPath = os.path.abspath( logFile)
  if not os.path.isdir( inDirPath):
    throwerr('inDir is not a dir: %s' % (inDirPath,))
  if not os.path.isdir( archDirPath):
    throwerr('archDir is not a dir: %s' % (archDirPath,))
  flog = open( logPath, 'a')
  # xxx use flog

  # Coord with uui in wrapUpload.sh
  uuiPattern = r'(arch\.date\.(\d{4}\.\d{2}\.\d{2})\.time\.(\d{2}\.\d{2}\.\d{2})\.userid\.(.*)\.hostname\.(.*)\.digest)'
  flagPattern = uuiPattern + r'\.flag'

  if func == 'createTableContrib':
    createTableContrib( buglev, dbhost, dbport, dbuser, dbpswd,
      dbname, dbschema, dbtablecontrib)

  elif func == 'readIncoming':
    while True:

      if buglev >= 1: logit('main: checking inDirPath: %s' % (inDirPath,))
      fnames = os.listdir( inDirPath)
      fnames.sort()
      for fname in fnames:
        mat = re.match( flagPattern, fname)
        if mat != None:
          wrapId = mat.group(1)
          dateStg = mat.group(2)
          timeStg = mat.group(3)
          userid = mat.group(4)
          hostname = mat.group(5)
          if buglev >= 1: logit('main: wrapId: %s' % (wrapId,))
          excArgs = None
          try: 
            gatherOne(
              buglev, inDirPath, archDirPath,
              wrapId, dateStg, timeStg, userid, hostname, inSpec,
              dbhost, dbport, dbuser, dbpswd, dbname,
              dbschema, dbtablecontrib)
          except Exception, exc:
            excArgs = exc.args
            logit('caught: %s' % (excArgs,))
            logit(traceback.format_exc( limit=None))

          if excArgs == None:
            logit('archived %s' % (wrapId,))
          else:
            logit('error for %s: %s' % (wrapId, excArgs,))
            throwerr( str(excArgs))

      time.sleep(10)

  # Re-process the subDirs under archDir.
  elif func == 'redoArch':
    fnames = os.listdir( archDirPath)
    fnames.sort()
    for fname in fnames:
      mat = re.match( uuiPattern, fname)
      if mat != None:
        wrapId = mat.group(1)
        dateStg = mat.group(2)
        timeStg = mat.group(3)
        userid = mat.group(4)
        hostname = mat.group(5)
        if buglev >= 1: logit('main: wrapId: %s' % (wrapId,))
        subDir = '%s/%s' % (archDirPath, wrapId,)
        excArgs = None
        try: 
          processOne(
            buglev, subDir, wrapId, dateStg, timeStg,
            userid, hostname, inSpec,
            dbhost, dbport, dbuser, dbpswd, dbname,
            dbschema, dbtablecontrib)
        except Exception, exc:
          excArgs = exc.args
          logit('caught: %s' % (excArgs,))
          logit(traceback.format_exc( limit=None))

        if excArgs == None:
          logit('archived %s' % (wrapId,))
        else:
          logit('error for %s: %s' % (wrapId, excArgs,))
          throwerr( str(excArgs))

  else: badparms('invalid func')




#====================================================================


def createTableContrib(
  buglev,
  dbhost,
  dbport,
  dbuser,
  dbpswd,
  dbname,
  dbschema,
  dbtablecontrib):

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

    cursor.execute('drop table if exists %s' % (dbtablecontrib,))
    conn.commit()

    cursor.execute('''
      CREATE TABLE %s (
        wrapid       text,
        adate        timestamp,
        userid       text,
        hostname     text,
        numincar     int,
        numvasprun   int,
        numoutcar    int,
        description  text
      )
    ''' % (dbtablecontrib,))
    conn.commit()
  finally:
    if cursor != None: cursor.close()
    if conn != None: conn.close()

  logit('wrapReceive.py: table created')


#====================================================================


def gatherOne(
  buglev, inDirPath, archDirPath,
  wrapId, dateStg, timeStg, userid, hostname, inSpec,
  dbhost, dbport, dbuser, dbpswd, dbname,
  dbschema, dbtablecontrib):

  if buglev >= 1:
    logit('gatherOne: inDirPath: %s' % (inDirPath,))
    logit('gatherOne: archDirPath: %s' % (archDirPath,))
    logit('gatherOne: wrapId: %s' % (wrapId,))

  # Check paths
  archPathOld = os.path.abspath( '%s/%s.tgz'  % (inDirPath, wrapId,))
  flagPathOld = os.path.abspath( '%s/%s.flag' % (inDirPath, wrapId,))
  if not os.access( archPathOld, os.R_OK):
    throwerr('cannot read file: %s' % (archPathOld,))
  if not os.access( flagPathOld, os.R_OK):
    throwerr('cannot read file: %s' % (flagPathOld,))

  # Move x.tgz and x.flag to subDir==archDir/wrapId
  subDir = '%s/%s' % (archDirPath, wrapId,)
  os.mkdir( subDir)
  shutil.copy2( archPathOld, subDir)
  shutil.copy2( flagPathOld, subDir)
  os.remove( archPathOld)
  os.remove( flagPathOld)

  archPathNew = os.path.abspath( '%s/%s.tgz'  % (subDir, wrapId,))
  flagPathNew = os.path.abspath( '%s/%s.flag' % (subDir, wrapId,))

  # Untar wrapId.tgz in subDir==archDir/wrapId

  proc = subprocess.Popen(
    ['/bin/tar', '-xzf', archPathNew],
    shell=False,
    cwd=subDir,
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    bufsize=10*1000*1000)
  (stdout, stderr) = proc.communicate()
  rc = proc.wait()
  if rc != 0:
    msg = 'tar failed.  rc: %d\n' % (rc,)
    msg += '\n===== stdout:\n%s\n' % (stdout,)
    msg += '\n===== stderr:\n%s\n' % (stderr,)
    throwerr( msg)

  processOne(
    buglev, subDir, wrapId, dateStg, timeStg,
    userid, hostname, inSpec,
    dbhost, dbport, dbuser, dbpswd, dbname,
    dbschema, dbtablecontrib)



#====================================================================



def processOne(
  buglev, subDir, wrapId, dateStg, timeStg,
  userid, hostname, inSpec,
  dbhost, dbport, dbuser, dbpswd, dbname,
  dbschema, dbtablecontrib):

  # Get adate
  adate = datetime.datetime.strptime(
    dateStg + ' ' + timeStg, '%Y.%m.%d %H.%M.%S')
  if buglev >= 1:
    logit('processOne: wrapId: %s' % (wrapId,))
    logit('processOne: adate: %s' % (adate,))
    logit('processOne: userid: "%s"' % (userid,))
    logit('processOne: hostname: "%s"' % (hostname,))

  # Get some statistics
  numIncar = findNumFiles('INCAR', subDir)
  numVasprun = findNumFiles('vasprun.xml', subDir)
  numOutcar = findNumFiles('OUTCAR', subDir)
  descFile = '%s/%s' % (subDir, 'digest.env/desc',)
  with open( subDir + '/digest.env/desc') as fin:
    desc = fin.read()
  desc = desc.strip()
  if buglev >= 1:
    logit('processOne: numIncar: %d' % (numIncar,))
    logit('processOne: numVasprun: %d' % (numVasprun,))
    logit('processOne: numOutcar: %d' % (numOutcar,))
    logit('processOne: desc: "%s"' % (desc,))

  # Process the digest file and add rows to the model table
  digestPath = '%s/%s' % (subDir, 'digest.pkl',)
  if not os.access( digestPath, os.R_OK):
    throwerr('cannot read file: %s' % (digestPath,))

  fillDbVasp.fillDbVasp(
    buglev,
    'fillTable',     # func
    digestPath,      # inDigest
    wrapId,
    inSpec)

  # Fill in additional columns in the model table
  augmentDb.augmentDb( buglev, wrapId, inSpec)

  # Update contrib table
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
    cursor.execute('set search_path to %s' % (dbschema,))
    cursor.execute('insert into ' + dbtablecontrib
      + ' (wrapid,adate,userid,hostname,numincar,numvasprun,'
      + 'numoutcar,description) values (%s,%s,%s,%s,%s,%s,%s,%s)',
      (wrapId, adate, userid, hostname, numIncar,
        numVasprun, numOutcar, desc,))
    conn.commit()
  finally:
    if cursor != None: cursor.close()
    if conn != None: conn.close()


#====================================================================

# Find the number of files with name==tag in tree at dir.
# Yes, Python has os.walk, but this is better.

def findNumFiles( tag, dir):
  if not os.path.isdir( dir): throwerr('not a dir: %s' % (dir,))
  nms = os.listdir( dir)
  nms.sort()
  count = 0
  for nm in nms:
    if nm == tag: count += 1
    subDir = dir + '/' + nm
    if os.path.isdir( subDir):
      count += findNumFiles( tag, subDir)      # recursion
  return count

#====================================================================


# Test if a process with the same program name as ours
# is already running.  If so, quit.
#
# Typical cmdline is: ['python', 'wrapReceive.py', ...]

def checkDupProcs():
  mypid = os.getpid()
  myproc = psutil.Process( mypid)
  mypgm = None
  mycmdline = myproc.cmdline
  if len(mycmdline) >= 2:
    mypgm = mycmdline[1]
    mypgmPath = os.path.abspath( mypgm)

  pids = psutil.get_pid_list()
  pids.sort()
  for pid in pids:
    proc = psutil.Process( pid)
    cmdline = proc.cmdline
    # print '\npid: %d  cmdline: %s' % (pid, cmdline,)
    if pid != mypid:
      if len(mycmdline) >= 2 and len(cmdline) >= 2:
        # print 'cmdline[0]: ', cmdline[0], '  cmdline[1]: ', cmdline[1]
        pgm = cmdline[1]
        pgmPath = os.path.abspath( pgm)
        if pgmPath == mypgmPath:
          throwerr('Apparently a duplicate process is already running.'
            + '  pid: %d  cmdline: %s  pgmPath: %s' % (pid, cmdline, pgmPath))


#====================================================================

# Print a logging message.
# Yes, Python has a logging package.
# This is better since it handles milliseconds
# and is far easier to use.

def logit(msg):
  tm = time.time()
  itm = int( math.floor( tm))
  delta = tm - itm
  loctm = time.localtime( itm)

  stg = time.strftime( '%Y-%m-%d %H:%M:%S', loctm)
  mdelta = int( math.floor( 1000 * delta))
  stg += '.%03d' % (mdelta,)

  print '%s %s' % (stg, msg,)

#====================================================================

def throwerr(msg):
  print 'Error: %s' % (msg,)
  raise Exception( msg)

#====================================================================

if __name__ == '__main__': main()

