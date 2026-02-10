#!/bin/sh
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

skip_taints=$1

echo "Deleting stuck pods..."

THRESHOLD=60
NOW=$(date -u +%s)

# 1) Terminating > THRESHOLD
kubectl get pods --all-namespaces -o json \
| jq -r \
    --argjson now "$NOW" \
    --argjson X "$THRESHOLD" \
'
  .items[]
  | select(.metadata.deletionTimestamp)
  | select( $now - ((.metadata.deletionTimestamp | fromdateiso8601)) > $X )
  | "\(.metadata.namespace) \(.metadata.name)"
' \
| xargs -r -n2 sh -c 'kubectl delete pod --grace-period=0 --force -n "$0" "$1"'

# 2) Failed pods with infra-related errors
kubectl get pods --all-namespaces --no-headers \
  | grep -E 'UnexpectedAdmissionError|OutOfcpu|Error|Unknown' \
  | awk '{print $1, $2}' \
  | xargs -r -n2 kubectl delete pod --grace-period=0 --force -n

# 3) Fallback Preemption: Delete all gitlab-runner pods on nodes with pending retina pods
# Get nodes with pending retina pods (node in spec.nodeName or status.nominatedNodeName)

# Using a loop because pods can died very quickly
endTime=$(( $(date +%s) + 10 ))
while [ $(date +%s) -lt $endTime ]; do
  nodes=$(kubectl get pods -n retina \
    --field-selector=status.phase=Pending \
    -o jsonpath='{range .items[*]}{.spec.nodeName}{" "}{.status.nominatedNodeName}{"\n"}{end}' \
    | tr ' ' '\n' \
    | grep -v '^$' \
    | sort -u)

  # For each node, delete gitlab-runner pods
  for node in $nodes; do
      # Skip nodes with specific taints
      taints=$(kubectl get node "$node" -o jsonpath='{range .spec.taints[*]}{.key}={.value};{end}')
      if echo "$taints" | grep -qE "$skip_taints|unreachable|not-ready|disk-pressure"; then
        continue
      fi
      kubectl get pods -n gitlab-runner \
        --field-selector=spec.nodeName="$node" \
        -o name \
      | xargs -r kubectl delete -n gitlab-runner
  done

  # Break loop if nodes were found
  if [ -n "$nodes" ]; then
    echo "Deleted gitlab-runner pods on nodes with pending retina pods: $nodes."
    break
  fi

done

echo "Done"

