

wrapUpload.sh
=============

Calls digestVasp.py to make a digest, named digest.pkl,
of all VASP results in the current directory tree.
Create a tar file containing the digest and many of the VASP
input and output files.
Use scp to upload the tar file to a wrapReceive.py process running
on the database server.

This script calls: digestVasp.py.

**Command line parameters:**
  none.

**Internal constants:**

  =================  =====================================================
  **digestVasp:**    The full path of digestVasp.py
  **targetdir:**     The target directory to upload to, such as:

                     ``scpuser@cid-dev.hpc.nrel.gov:/data/incoming``
  =================  =====================================================

  The directory containing digestVasp.py must also contain readVasp.py


