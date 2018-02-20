#!/bin/sh
# ---------------------------------------------------------------------
# This is an example install script.  Typically package install
# actions go in here apt-get, dnf, yum, pip install
# etc., but anything can be run here.  Return a non zero value and the
# err_install.sh script will be invoked.
# ---------------------------------------------------------------------
echo "install running...."
echo "sleep 1 second"
ping -c 1 google.ca
sleep 1
exit 0
