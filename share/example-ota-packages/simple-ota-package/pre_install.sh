#!/bin/sh
# ------------------------------------------------------------------
# This is an example pre install script.  This script holds logic
# that prepare the system for an OTA operation.  If this script
# returns a non zero value, the err_install.sh script will be invoked.
# ------------------------------------------------------------------
echo "Extra parameters:"
echo "$HDC_EXTRA_PARAMS"
echo "pre install running..."
echo "Sleep 1 second"
sleep 1
exit 0
