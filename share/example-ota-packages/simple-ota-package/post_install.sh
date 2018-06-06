#!/bin/sh
# ---------------------------------------------------------------------
# This script will run after the install.sh script.  Typically, this
# script is used for clean or anything that does not belong in the
# install script.
# ---------------------------------------------------------------------
echo "Extra parameters:"
echo "$HDC_EXTRA_PARAMS"

echo "post install running....."
echo "Sleep 1 second"
sleep 1
exit 0
