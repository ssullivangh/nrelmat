

====================================
NREL MatDB Database Overview
====================================


The NREL MatDB stores and retrieves the results
of molecular modeling programs such as VASP_.

.. _VASP: https://www.vasp.at/


VASP
======

Our initial implementation is for VASP output,
so let's focus on VASP.

VASP requires the following input files, although
it can use many more:


  * INCAR: Main list of parameters.
  * KPOINTS: Specify the k-point grid.
  * POSCAR: Specify atom positions.
  * POTCAR: Specify atomic pseudopotentials.

VASP produces many output files, but the only two we retain
are:

  * OUTCAR: General log and results in human-readable format.
  * vasprun.xml: All results in XML format.


During a study a researcher may produce terabytes of VASP-related
information: for each of many structures, multiple VASP runs
perform different relaxations.

Typically a group of related directories will be uploaded
at once.  They are identified by a wrapId.


wrapId
================

A wrapId uniquely identifies a single invocation of wrapUpload.py
to upload a group of directories.
A typical wrapId is: ::

    @2013.08.13@12.58.22.735311@someUser@home.someUser.redmesa.old.td.testlada.2013.04.06.Fe.O@

The wrapId broken into fields separated by "@":

  * Date, yyyy.mm.dd
  * Time, hh.mm.ss.uuuuuu  where uuuuuu is microseconds padded to 6 characters
  * User name.
  * Top directory specified to wrapUpload, with "/" replaced by ".".



wrapUpload.py
================

A researcher runs the Python program wrapUpload.py to
upload results to the server.
The program takes as input either ...

  * A directory tree, in which case command line parameters
    control which subdirectories are accepted for uploading.
  * A list of specific directories to upload.

The wrapUpload program creates a unique identifier
for this upload, called the **wrapId**.

Then wrapUpload makes a list of all files to be
uploaded.  These must be in directories that passed the
filters above and is restricted to the files:

  * metadata: user-specified metadata like name and publication DOI.
  * INCAR: Main list of parameters.
  * KPOINTS: Specify the k-point grid.
  * POSCAR: Specify atom positions.
  * POTCAR: Specify atomic pseudopotentials.
  * OUTCAR: General log and results in human-readable format.
  * vasprun.xml: All results in XML format.

Then wrapUpload makes a single ``tar.gz`` file
of all the files, and uses ``scp`` to upload three files:

  * wrapId.json: General statistics and information
  * wrapId.tgz: Compendium of all files to be archived.
  * wrapId.flag: Zero-length flag.

The wrapId.flag file gets uploaded last.  The server doesn't
start processing the files until receiving the flag file,
thereby preventing the server from starting
to process partly-received data.


wrapReceive.py
----------------

The server runs a single Python program: wrapReceive.py.
Every few seconds wrapReceive checks for files in the 
directory /data/incoming.  If it finds a file there having
the format ``wrapId.flag``, ...

  * It checks that the three files are present:

    * wrapId.json: General statistics and information
    * wrapId.tgz: Compendium of all files to be archived.
    * wrapId.flag: Zero-length flag.

  * It creates a directory /data/arch/wrapId, and moves
    moves the three files from /data/incoming to /data/arch/wrapId.

  * Within directory /data/arch/wrapId ...
  * It untars wrapId.tgz to subdirectory vdir
  * It calls fillDbVasp.py, passing the directory /data/arch/wrapId.


fillDbVasp.py
----------------

The fillDbVasp program has three possible main functions:

  * Delete and recreate the ``model`` database table.
    This function is rarely used.

  * Delete and recreate the ``contrib`` database table.
    This function is rarely used.

  * Analyze the contents of a directory corresponding to
    a single wrapId, and ingest the data into the database.
    This is the function invoked by wrapReceive.py.

Continuing with the third choice,

For each relative subdir specified in the wrapId.json file,
fillDbVasp finds the reconstructed directory and calls
fillRow to handle the directory.
The fillRow method calls readVasp.py to read the vasprun.xml file.
The readVasp.py program returns a map (Python dictionary)
and adds a single row to the model table.

Finally, fillDbVasp adds a single row to the contrib
table with information about the wrapId covering the entire
set of directories.



