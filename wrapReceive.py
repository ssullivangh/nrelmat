#!/usr/bin/env python

import datetime, json, math, os, re
import shutil, sys, time, traceback
import psutil
import psycopg2
import fillDbVasp
import augmentDb
import wrapUpload



#====================================================================


def badparms( msg):
  print '\nError: %s' % (msg,)
  print 'Parms:'
  print ''
  print '  -bugLev     <int>      debug level'
  print '  -func       <string>   readIncoming / redoArch'
  print '  -inDir      <string>   Input dir for uploaded files.'
  print '  -archDir    <string>   Dir used for work and archiving.'
  print '  -logFile    <string>   Log file name.'
  print '  -inSpec     <string>   inSpecJsonFile'
  print '  -archDir    <string>   dir for archiving'
  print '  -inSpec     <string>   inSpecJsonFile'
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
  **-bugLev**     integer      Debug level.  Normally 0.
  **-func**       string       Function.  See below.
  **-inDir**      string       Input dir for uploaded files.
  **-archDir**    string       Dir used for work and archiving.
  **-logFile**    string       Log file name.
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

  bugLev = None
  func = None
  inDir = None
  archDir = None
  logFile = None
  inSpec = None

  if len(sys.argv) % 2 != 1:
    badparms('Parms must be key/value pairs')
  for iarg in range( 1, len(sys.argv), 2):
    key = sys.argv[iarg]
    val = sys.argv[iarg+1]
    if key == '-bugLev': bugLev = int( val)
    elif key == '-func': func = val
    elif key == '-inDir': inDir = val
    elif key == '-archDir': archDir = val
    elif key == '-logFile': logFile = val
    elif key == '-inSpec': inSpec = val
    else: badparms('unknown key: "%s"' % (key,))

  if bugLev == None: badparms('parm not specified: -bugLev')
  if func == None: badparms('parm not specified: -func')
  if inDir == None: badparms('parm not specified: -inDir')
  if archDir == None: badparms('parm not specified: -archDir')
  if logFile == None: badparms('parm not specified: -logFile')
  if inSpec == None: badparms('parm not specified: -inSpec')

  print 'wrapReceive: func: %s' % (func,)
  print 'wrapReceive: inDir: %s' % (inDir,)
  print 'wrapReceive: archDir: %s' % (archDir,)
  print 'wrapReceive: logFile: %s' % (logFile,)
  print 'wrapReceive: inSpec: %s' % (inSpec,)

  inDirPath = os.path.abspath( inDir)
  archDirPath = os.path.abspath( archDir)
  logPath = os.path.abspath( logFile)
  if not os.path.isdir( inDirPath):
    throwerr('inDir is not a dir: %s' % (inDirPath,))
  if not os.path.isdir( archDirPath):
    throwerr('archDir is not a dir: %s' % (archDirPath,))

  flog = open( logPath, 'a')
  # xxx use flog


  # Quit if there's a duplicate process already running.
  checkDupProcs()


  # Coord with uui in wrapUpload.sh
  uuiPattern = r'^(arch\.(\d{4}\.\d{2}\.\d{2})\.tm\.(\d{2}\.\d{2}\.\d{2}\.\d{6})\.user\.(.*)\.host\.(.*)\.digest)'
  flagPattern = uuiPattern + r'\.flag'

  if func == 'readIncoming':
    while True:

      if bugLev >= 1:
        wrapUpload.logit('main: checking inDirPath: %s' % (inDirPath,))
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
          if bugLev >= 1: wrapUpload.logit('main: wrapId: %s' % (wrapId,))
          excArgs = None
          try: 
            gatherArchive(
              bugLev, inDirPath, archDirPath,
              wrapId, dateStg, timeStg, userid, hostname, inSpec)
          except Exception, exc:
            excArgs = exc.args
            wrapUpload.logit('caught: %s' % (excArgs,))
            wrapUpload.logit(traceback.format_exc( limit=None))

          if excArgs == None:
            wrapUpload.logit('archived %s' % (wrapId,))
          else:
            wrapUpload.logit('error for %s: %s' % (wrapId, excArgs,))
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
        if bugLev >= 1: wrapUpload.logit('main: wrapId: %s' % (wrapId,))
        subDir = os.path.join( archDirPath, wrapId)
        excArgs = None
        try: 
          processTree(
            bugLev, subDir, wrapId, dateStg, timeStg,
            userid, hostname, inSpec)
        except Exception, exc:
          excArgs = exc.args
          wrapUpload.logit('caught: %s' % (excArgs,))
          wrapUpload.logit(traceback.format_exc( limit=None))

        if excArgs == None:
          wrapUpload.logit('archived %s' % (wrapId,))
        else:
          wrapUpload.logit('error for %s: %s' % (wrapId, excArgs,))
          throwerr( str(excArgs))

  else: badparms('invalid func')




#====================================================================

def gatherArchive(
  bugLev, inDirPath, archDirPath,
  wrapId, dateStg, timeStg, userid, hostname, inSpec):

  if bugLev >= 1:
    wrapUpload.logit('gatherArchive: inDirPath: %s' % (inDirPath,))
    wrapUpload.logit('gatherArchive: archDirPath: %s' % (archDirPath,))
    wrapUpload.logit('gatherArchive: wrapId: %s' % (wrapId,))

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
    bugLev, subDir, wrapId, dateStg, timeStg,
    userid, hostname, inSpec)



#====================================================================



def processTree(
  bugLev, subDir, wrapId, dateStg, timeStg,
  userid, hostname, inSpec):

  # Get adate
  adate = datetime.datetime.strptime(
    dateStg + ' ' + timeStg, '%Y.%m.%d %H.%M.%S.%f')
  if bugLev >= 1:
    wrapUpload.logit('processTree: wrapId: %s' % (wrapId,))
    wrapUpload.logit('processTree: subDir: %s' % (subDir,))
    wrapUpload.logit('processTree: adate: %s' % (adate,))
    wrapUpload.logit('processTree: userid: "%s"' % (userid,))
    wrapUpload.logit('processTree: hostname: "%s"' % (hostname,))

  fillDbVasp.fillDbVasp(
    bugLev,
    'fillTable',     # func
    subDir,
    wrapId,
    inSpec)

  # Fill in additional columns in the model table
  augmentDb.augmentDb( bugLev, wrapId, inSpec)


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

