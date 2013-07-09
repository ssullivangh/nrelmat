#!/usr/bin/env python

import datetime, json, math, os, re
import shutil, sys, time, traceback
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
  print '  -func       <string>   readIncoming / redoArch'
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

  **readIncoming**
    Monitor the inDir for new additions.
    When one is found, move it to archDir, untar it,
    and run fillDbVasp.py on the digest.pkl file
    to insert the results into the model table.
    Also insert a row into the contrib table for this wrapId.

  **redoArch**
    Re-process all the subDirs found in archDir.
    This is useful when someone changes the database tables,
    for example by adding an new column.
    Then one can use the following to recreate the tables
    with the new column.

      fillDbTable.py -func createTableModel
      fillDbTable.py -func createTableContrib
      wrapReceive.py -func redoArch

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
  note = None

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if key == '-buglev': buglev = int( val)
    elif key == '-func': func = val
    elif key == '-inSpec': inSpec = val
    elif key == '-note': note = val
    else: badparms('unknown key: "%s"' % (key,))

  if buglev == None: badparms('parm not specified: -buglev')
  if func == None: badparms('parm not specified: -func')
  if inSpec == None: badparms('parm not specified: -inSpec')
  if note == None: badparms('parm not specified: -note')

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

xxx del all dbtablecontrib, etc?
  if dbtablecontrib == None: badparms('inSpec name not found: dbtablecontrib')

  if dbtablemodel   == None: badparms('inSpec name not found: dbtablemodel')
  dbport = int( dbport)


  # Quit if there's a duplicate process already running.
  print 'xxxxxxxxxxxx checkDupProcs omitted'
  ##checkDupProcs()

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
  uuiPattern = r'^(arch\.(\d{4}\.\d{2}\.\d{2})\.tm\.(\d{2}\.\d{2}\.\d{2}\.\d{6})\.user\.(.*)\.host\.(.*)\.digest)'
  flagPattern = uuiPattern + r'\.flag'

  if func == 'readIncoming':
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
            gatherArchive(
              buglev, inDirPath, archDirPath,
              wrapId, dateStg, timeStg, userid, hostname, inSpec, note,
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
        subDir = os.path.join( archDirPath, wrapId)
        excArgs = None
        try: 
          processTree(
            buglev, subDir, wrapId, dateStg, timeStg,
            userid, hostname, inSpec, note,
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



#====================================================================


def gatherArchive(
  buglev, inDirPath, archDirPath,
  wrapId, dateStg, timeStg, userid, hostname, inSpec, note,
  dbhost, dbport, dbuser, dbpswd, dbname,
  dbschema, dbtablecontrib):

  if buglev >= 1:
    logit('gatherArchive: inDirPath: %s' % (inDirPath,))
    logit('gatherArchive: archDirPath: %s' % (archDirPath,))
    logit('gatherArchive: wrapId: %s' % (wrapId,))

  # Check paths
  archPathOld = os.path.abspath( os.path.join( inDirPath, wrapId+'.tgz'))
  flagPathOld = os.path.abspath( os.path.join( inDirPath, wrapId+'.flag'))
  wrapUpload.checkFileFull( archPathOld)
  wrapUpload.checkFile( flagPathOld)

  # Move x.tgz and x.flag to subDir==archDir/wrapId
  subDir = os.path.join( archDirPath, wrapId)
  os.mkdir( subDir)
  shutil.copy2( archPathOld, subDir)
  shutil.copy2( flagPathOld, subDir)
  os.remove( archPathOld)
  os.remove( flagPathOld)

  archPathNew = os.path.abspath( os.path.join( subDir, wrapId+'.tgz'))
  flagPathNew = os.path.abspath( os.path.join( subDir, wrapId+'.flag'))

  # Untar wrapId.tgz in subDir==archDir/wrapId

  args = ['/bin/tar', '-xzf', archPathNew]
  wrapUpload.runSubprocess( bugLev, subDir, args)

  processTree(
    buglev, subDir, wrapId, dateStg, timeStg,
    userid, hostname, inSpec, note,
    dbhost, dbport, dbuser, dbpswd, dbname,
    dbschema, dbtablecontrib)



#====================================================================



def processTree(
  buglev, subDir, wrapId, dateStg, timeStg,
  userid, hostname, inSpec, note,
  dbhost, dbport, dbuser, dbpswd, dbname,
  dbschema, dbtablecontrib):

  # Get adate
  adate = datetime.datetime.strptime(
    dateStg + ' ' + timeStg, '%Y.%m.%d %H.%M.%S.%f')
  if buglev >= 1:
    logit('processTree: wrapId: %s' % (wrapId,))
    logit('processTree: subDir: %s' % (subDir,))
    logit('processTree: adate: %s' % (adate,))
    logit('processTree: userid: "%s"' % (userid,))
    logit('processTree: hostname: "%s"' % (hostname,))

xxxxxxxxxxx
  print 'xxxxxxxxxxxxxxxxxxxxxxxxxxxx skip fillDbVasp xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
  #fillDbVasp.fillDbVasp(
  #  buglev,
  #  'fillTable',     # func
  #  subDir,
  #  wrapId,
  #  inSpec)


  # Fill in additional columns in the model table
  augmentDb.augmentDb( buglev, wrapId, inSpec)

xxxxxxxxx del:
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

def throwerr(msg):
  print 'Error: %s' % (msg,)
  raise Exception( msg)

#====================================================================

if __name__ == '__main__': main()

