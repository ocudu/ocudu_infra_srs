#!/bin/bash
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

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
SCRIPT_FOLDER=$OLDPWD
echo script folder: $SCRIPT_FOLDER

terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json

RUNNERS=$(jq -r '
.resource_changes[]
| select(.change.actions | index("create") or index("update") or index("delete"))
| .address
| split(".")
| .[1]
' tfplan.json
)

if [ -z "$RUNNERS" ]; then
  echo "No RUNNERS to be modified. Exiting normally..."
  exit 0
fi

export PYTHONUNBUFFERED=1 # so Python prints happen immediately in the job log

pids=()
declare -A pid_to_runner

# Launch all runner processes in parallel
for runner_name in $RUNNERS; do
   echo "Pausing runner $runner_name, waiting for its jobs to finish and, if timeout, cancelling them..."
  ${SCRIPT_FOLDER}/runner_pause_wait_unpause.py --runner-name "$runner_name" --token "$RUNNER_UPDATE_TOKEN" --pause_wait --wait_minutes 1 --runners-def "$RUNNERS_DEF_PATH" &
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
    for runner_name in $RUNNERS; do
      echo "Unpausing runner $runner_name..."
      ${SCRIPT_FOLDER}/runner_pause_wait_unpause.py --runner-name "$runner_name" --token "$RUNNER_UPDATE_TOKEN" --unpause --runners-def "$RUNNERS_DEF_PATH" &
    done
    wait
    echo "Runners unpaused. Exiting with error code 1..."
    exit 1
  fi
done

echo "All runner processes finished successfully."

# This (3) applies the changes (for all the affected runners)
terraform apply -auto-approve tfplan

for runner_name in $RUNNERS; do
  echo "Unpausing runner $runner_name..."
  # This (4) unpauses the runner.
  ${SCRIPT_FOLDER}/runner_pause_wait_unpause.py --runner-name "$runner_name" --token "$RUNNER_UPDATE_TOKEN" --unpause --runners-def "$RUNNERS_DEF_PATH" &
done

wait

echo "Runners unpaused..."