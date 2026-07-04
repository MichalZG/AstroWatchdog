#!/bin/sh

if [ ! -e ~/.ssh/id_eps_rsa ]; then
	mkdir -p ~/.ssh/
	TEMP=$(mktemp -d)
	scp observer@epsilon:.ssh/id_rsa* $TEMP/
	mv $TEMP/id_rsa ~/.ssh/id_eps_rsa
	mv $TEMP/id_rsa.pub ~/.ssh/id_eps_rsa.pub
	rm -rf $TEMP
fi  


eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_eps_rsa

tmpdir=`mktemp -d`
if [ $# -gt 0 ]; then
  destdir=$1
else
  destdir=$HOME
fi
trap ":" INT

seconds=2 # or however many seconds you like

while sleep $seconds ; do
  rsync -c --progress --temp-dir="$tmpdir/" observer@192.168.2.3:/home/observer/.jastrocam3/preview.fits $destdir
  if [ $? -ne 0 ] ; then
     sleep 300
  fi
done
\rm -fr $tmpdir
