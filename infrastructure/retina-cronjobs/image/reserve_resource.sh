#!/bin/sh
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

RESOURCE=$1
export LOGNAME=daily_dev

echo "Checking resource $RESOURCE to reserve it for $LOGNAME..."

while true; do
   # Select the "Reserved by" value from "retina --in-cluster status" output where entry contains RESOURCE
   reserved_by=$(
      retina --in-cluster status \
         | grep $RESOURCE \
         | awk -F'│' '{gsub(/^[ \t]+|[ \t]+$/,"",$3); print $3}'
   )

   if [ "$reserved_by" = "$LOGNAME" ]; then
      echo "Resource is reserved by us ($LOGNAME). Exiting..."
      exit
   elif [ -z "$reserved_by" ]; then
      echo "Resource is free; reserving it..."
      retina --in-cluster reserve $RESOURCE
   else
      echo "Resource is reserved by $reserved_by; waiting 5 seconds to check again..."
      sleep 5
   fi
done

