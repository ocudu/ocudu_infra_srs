#!/bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

echo "Runner quarantine-apply script started."

WORKDIR="$1"
RUNNERS_DEF_PATH="$2"
echo workdir: $WORKDIR
echo runners_def_path: $RUNNERS_DEF_PATH

if [ -z "$RUNNERS_DEF_PATH" ]; then
  echo "Error: Runners definition path is required as second argument"
  exit 1
fi

echo before cd WORKDIR
echo pwd: $(pwd)
echo oldpwd: $OLDPWD

cd "$WORKDIR" || { echo "Failed to change directory to $WORKDIR"; exit 1; }

echo after cd WORKDIR
echo pwd: $(pwd)
echo oldpwd: $OLDPWD
SCRIPT_FOLDER=$(dirname "$(readlink -f "$0")")
echo script folder: $SCRIPT_FOLDER

terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json

# Runners being created or updated — these exist in the YAML and need pause/unpause
RUNNERS_TO_PAUSE=$(jq -r '
.resource_changes[]
| select(.change.actions != ["delete"])
| select(.change.actions | index("create") or index("update") or index("delete"))
| .address
| split(".")
| .[1]
' tfplan.json
)

# Runners being destroyed only — no longer in the YAML, skip pause/unpause
RUNNERS_TO_DESTROY=$(jq -r '
.resource_changes[]
| select(.change.actions == ["delete"])
| .address
| split(".")
| .[1]
' tfplan.json
)

if [ -z "$RUNNERS_TO_PAUSE" ] && [ -z "$RUNNERS_TO_DESTROY" ]; then
  echo "No RUNNERS to be modified. Exiting normally..."
  exit 0
fi

if [ -n "$RUNNERS_TO_DESTROY" ]; then
  echo "Runners being destroyed (skipping pause/unpause — no longer in runners definition):"
  for runner_name in $RUNNERS_TO_DESTROY; do
    echo "  - $runner_name"
  done
fi

export PYTHONUNBUFFERED=1 # so Python prints happen immediately in the job log

pids=()
declare -A pid_to_runner

# Launch pause processes only for runners that are still in the YAML (create/update)
for runner_name in $RUNNERS_TO_PAUSE; do
  echo "Pausing runner $runner_name, waiting for its jobs to finish and, if timeout, cancelling them..."
  python ${SCRIPT_FOLDER}/runner_pause_wait_unpause.py --runner-name "$runner_name" --token "$RUNNER_UPDATE_TOKEN" --pause_wait --wait_minutes 1 --runners-def "$RUNNERS_DEF_PATH" &
  pid=$!
  pids+=("$pid")
  pid_to_runner["$pid"]="$runner_name"
done

# Wait on each PID, remove all of them if one fails
for pid in "${pids[@]}"; do
  if wait "$pid"; then
    echo "Process for runner ${pid_to_runner[$pid]} succeeded!"
  else
    echo "Process for runner ${pid_to_runner[$pid]} failed! — killing remaining processes..."
    for other_pid in "${pids[@]}"; do
      if [[ "$other_pid" != "$pid" ]] && kill -0 "$other_pid" 2>/dev/null; then
        echo "Force killing PID $other_pid (${pid_to_runner[$other_pid]})"
        kill -9 "$other_pid" 2>/dev/null
      fi
    done
    echo "Runner processes finished with errors. Unpausing runners..."
    for runner_name in $RUNNERS_TO_PAUSE; do
      echo "Unpausing runner $runner_name..."
      python ${SCRIPT_FOLDER}/runner_pause_wait_unpause.py --runner-name "$runner_name" --token "$RUNNER_UPDATE_TOKEN" --unpause --runners-def "$RUNNERS_DEF_PATH" &
    done
    wait
    echo "Runners unpaused. Exiting with error code 1..."
    exit 1
  fi
done

echo "All runner processes finished successfully."

# Apply all changes (creates, updates, AND destroys)
terraform apply -auto-approve tfplan

# Unpause only runners that are still in the YAML (not destroyed ones)
for runner_name in $RUNNERS_TO_PAUSE; do
  echo "Unpausing runner $runner_name..."
  python ${SCRIPT_FOLDER}/runner_pause_wait_unpause.py --runner-name "$runner_name" --token "$RUNNER_UPDATE_TOKEN" --unpause --runners-def "$RUNNERS_DEF_PATH" &
done

wait

echo "Runners unpaused..."