#!/bin/sh
# ------------------------------------------------------------------
# This is an example error recovery script.  This script holds logic
# that will recover from an OTA operation.  Any install script that
# returns a non zero value will invoke this script.
# ------------------------------------------------------------------
echo "Extra parameters:"
echo "$HDC_EXTRA_PARAMS"

echo "something went wrong, recovering..."
echo "sleep 1 second"
sleep 1
exit 0
