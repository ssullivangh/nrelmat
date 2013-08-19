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

import datetime, json, math, os, re
import shutil, sys, time, traceback
import psutil
import psycopg2
import fillDbVasp
import augmentDb
import wrapUpload


#====================================================================


vdirName = 'vdir'

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
  sys.exit(1)


#====================================================================



def main():
  '''
  This is the receiver for data uploaded by wrapUpload.py.

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
    Every few seconds list the files in inDir.
    For each file name matching ``wrapId.flag``, call function
    :func:`gatherArchive` to process the three files:
    ``wrapId.json``, ``wrapId.tgz``, and ``wrapId.flag``.
    Since program :mod:`wrapUpload` always writes
    the flag file last, the other two should already be present.

  **redoArch**
    Re-process all the subDirs found in archDir by calling
    function :func:`processTree` for each subDir.
    This is useful when someone changes the database tables,
    for example by adding an new column.
    Then one can use the following to recreate the tables
    with the new column. ::

      fillDbVasp.py -func createTableModel -deleteTable true
      fillDbVasp.py -func createTableContrib -deleteTable true
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

  if func == 'readIncoming':
    while True:

      if bugLev >= 1:
        wrapUpload.logit('main: checking inDirPath: %s' % (inDirPath,))
      fnames = os.listdir( inDirPath)
      fnames.sort()
      for fname in fnames:
        # If matches, returns (wrapId, adate, userid, hostname).
        wrapId = wrapUpload.parseUui( fname)
        if wrapId != None and fname.endswith('.flag'):
          if bugLev >= 1: wrapUpload.logit('main: wrapId: %s' % (wrapId,))

          excStg = None
          try: 
            gatherArchive(
              bugLev, inDirPath, archDirPath, wrapId, inSpec)
          except Exception, exc:
            excStg = repr( exc)
            wrapUpload.logit('caught: %s' % (excStg,))
            wrapUpload.logit(traceback.format_exc( limit=None))

          if excStg == None:
            wrapUpload.logit('archived %s' % (wrapId,))
          else:
            wrapUpload.logit('error for %s: %s' % (wrapId, excStg,))
            # throwerr( excStg)

      time.sleep(5)                     # poll interval

  # Re-process the subDirs under archDir.
  elif func == 'redoArch':
    fnames = os.listdir( archDirPath)
    fnames.sort()
    for fname in fnames:
      # If matches, returns (wrapId, adate, userid, hostname).
      wrapId = wrapUpload.parseUui( fname)
      if wrapId != None:
        if bugLev >= 1: wrapUpload.logit('main: wrapId: %s' % (wrapId,))
        subDir = os.path.join( archDirPath, wrapId)

        excStg = None
        try: 
          processTree( bugLev, subDir, wrapId, inSpec)
        except Exception, exc:
          excStg = repr( exc)
          wrapUpload.logit('caught: %s' % (excStgs,))
          wrapUpload.logit(traceback.format_exc( limit=None))

        if excStgs == None:
          wrapUpload.logit('archived %s' % (wrapId,))
        else:
          wrapUpload.logit('error for %s: %s' % (wrapId, excStgs,))
          throwerr( excStg)

  else: badparms('invalid func')



#====================================================================


def gatherArchive(
  bugLev, inDirPath, archDirPath, wrapId, inSpec):
  '''
  Moves inDirPath/wrapId.* to archDir and adds the info to the database.

  Moves inDirPath/wrapId{.json,.tgz,.flag} to the new dir archDir/wrapId.
  Untars the .tgz file.
  Then calls function :func:`processTree` to add the info to the database.

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.
  * inDirPath (str): Absolute path of the command line parm ``inDir``.
  * archDirPath (str): Absolute path of the command line parm ``archDir``.
  * wrapId (str): The wrapId extracted from the current filename.
  * inSpec (str): Name of JSON file containing DB parameters.
                  See description at :func:`main`.

  **Returns**

  * None
  '''

  if bugLev >= 1:
    wrapUpload.logit('gatherArchive: inDirPath: %s' % (inDirPath,))
    wrapUpload.logit('gatherArchive: archDirPath: %s' % (archDirPath,))
    wrapUpload.logit('gatherArchive: wrapId: %s' % (wrapId,))

  # Check paths
  jsonPathOld = os.path.abspath( os.path.join( inDirPath, wrapId+'.json'))
  archPathOld = os.path.abspath( os.path.join( inDirPath, wrapId+'.tgz'))
  flagPathOld = os.path.abspath( os.path.join( inDirPath, wrapId+'.flag'))
  wrapUpload.checkFileFull( jsonPathOld)
  wrapUpload.checkFileFull( archPathOld)
  wrapUpload.checkFile( flagPathOld)

  # Move (actually copy, then remove the old one)
  # x.json, x.tgz, x.flag to subDir==archDir/wrapId
  subDir = os.path.join( archDirPath, wrapId)
  os.mkdir( subDir)
  shutil.copy2( jsonPathOld, subDir)
  shutil.copy2( archPathOld, subDir)
  shutil.copy2( flagPathOld, subDir)
  os.remove( jsonPathOld)
  os.remove( archPathOld)
  os.remove( flagPathOld)

  jsonPathNew = os.path.abspath( os.path.join( subDir, wrapId+'.json'))
  archPathNew = os.path.abspath( os.path.join( subDir, wrapId+'.tgz'))
  flagPathNew = os.path.abspath( os.path.join( subDir, wrapId+'.flag'))

  vdir = os.path.join( subDir, vdirName)
  os.mkdir( vdir)

  # Untar wrapId.tgz in subDir==archDir/wrapId

  args = ['/bin/tar', '-xzf', archPathNew]
  wrapUpload.runSubprocess( bugLev, vdir, args, False)  # print stdout = False

  # xxx Here we could delete archPathNew.

  processTree( bugLev, subDir, wrapId, inSpec)



#====================================================================



def processTree( bugLev, subDir, wrapId, inSpec):
  '''
  Calls :mod:`fillDbVasp` to add info to the database,
  and :mod:`augmentDb` to fill additional DB columns.

  **Parameters**:

  * bugLev (int): Debug level.  Normally 0.
  * wrapId (str): The wrapId extracted from the current filename.
  * subDir (str): archDirPath/wrapId
  * inSpec (str): Name of JSON file containing DB parameters.
                  See description at :func:`main`.

  **Returns**

  * None
  '''

  if bugLev >= 1:
    wrapUpload.logit('processTree: wrapId: %s' % (wrapId,))
    wrapUpload.logit('processTree: subDir: %s' % (subDir,))

  fillDbVasp.fillDbVasp(
    bugLev,
    'fillTable',     # func
    False,           # deleteTable
    subDir,
    wrapId,
    inSpec)

  # Fill in additional columns in the model table
  augmentDb.augmentDb( bugLev, inSpec)


#====================================================================


def checkDupProcs():
  '''
  Tests if a process with the same program name as ours
  is already running, and if so, quits.

  **Parameters**:

  * None

  **Returns**

  * None

  **Raises**

  * Exception (via throwerr) if another process has the same name.
  '''

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
  '''
  Prints an error message and raises Exception.

  **Parameters**:

  * msg (str): Error message.

  **Returns**

  * (Never returns)
  
  **Raises**

  * Exception
  '''

  print 'Error: %s' % (msg,)
  raise Exception( msg)

#====================================================================

if __name__ == '__main__': main()

