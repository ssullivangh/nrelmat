#!/bin/bash

# Calls digestVasp.py to make a digest, named digest.pkl,
# of all VASP results in the current directory tree.
# Create a tar file containing the digest and many of the VASP
# input and output files.
# Use scp to upload the tar file to a wrapReceive.py process running
# on the database server.

digestVasp=/home/ssulliva/stuff/cidvasp/digestVasp.py
targetDir=scpuser@cid-dev.hpc.nrel.gov:/data/incoming

set -e

if [ "$VISUAL" != "" ]; then
  useEditor=$VISUAL
elif [ "$EDITOR" != "" ]; then
  useEditor=$EDITOR
else
  echo ''
  echo 'Sorry, you have not set a preferred editor.'
  echo 'Please set a preferred editor and try again.'
  echo 'To set a preferred editor in bash or sh use for example:'
  echo '    export EDITOR=vi'
  echo 'To set a preferred editor in csh or tcsh use for example:'
  echo '    setenv EDITOR emacs'
  exit 1
fi

uploadDir=.
#uploadDir=~/cidUpload
#if [ ! -d $uploadDir ]; then
#  mkdir $uploadDir
#fi

rm -rf digest.env
mkdir digest.env

echo '===== wrapUpload.sh: begin digest.env/desc'
echo 'Please delete this line and enter a short summary of this upload.' \
  > digest.env/desc
$useEditor digest.env/desc

echo '===== wrapUpload.sh: begin digest.env/misc'
printenv | sort > digest.env/printenv_sort
uname -a > digest.env/uname_-a
cp /proc/cpuinfo digest.env/proc_cpuinfo
pwd > digest.env/pwd
whoami > digest.env/whoami

echo '===== wrapUpload.sh: begin digestVasp.py'
/usr/bin/time $digestVasp -buglev 1 -func fillTree \
  -readType xml \
  -inDir . \
  -outDigest digest.pkl > digest.log

# Coord with uuiPattern in wrapReceive.py
uui=arch.date.$(date +%Y.%m.%d.time.%H.%M.%S).userid.$(whoami).hostname.$(uname -n).digest
  # We could add: .uui.$(uuidgen -r)
echo '===== wrapUpload.sh: The wrapId is ' $uui

echo '===== wrapUpload.sh: begin tar'
/usr/bin/find . -type f \
  | sort \
  | /bin/egrep 'CHG$|CONTCAR$|INCAR$|KPOINTS$|OUTCAR$|POSCAR$|pbserr$|pbsout$|stderr$|stdout$|vasprun\.xml$|digest\.env$|digest\.log$|digest\.pkl$|' \
  | xargs tar czf $uploadDir/$uui.tgz


# Require user confirm so the user doesn't walk off and 
# scp gives timeout while waiting for a password.
echo ''
read -p '===== Press enter to begin uploading.'
/bin/rm -f $uploadDir/$uui.flag
touch $uploadDir/$uui.flag

scp  $uploadDir/$uui.tgz  $uploadDir/$uui.flag $targetDir

echo ''
echo '===== wrapUpload.sh: Thank you.  Your archive was uploaded.'
echo '===== wrapUpload.sh: The wrapId is' $uui
