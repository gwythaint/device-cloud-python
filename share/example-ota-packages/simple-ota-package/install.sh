#!/bin/sh
# ---------------------------------------------------------------------
# This is an example install script.  Typically package install
# actions go in here apt-get, dnf, yum, pip install
# etc., but anything can be run here.  Return a non zero value and the
# err_install.sh script will be invoked.
# ---------------------------------------------------------------------
echo "Extra parameters:"
echo "$HDC_EXTRA_PARAMS"
echo "install running...."
ping -c 1 google.ca
exit 0
