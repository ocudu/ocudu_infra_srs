#!/usr/bin/env python3
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
GitLab Runner Pause/Wait/Unpause Script
"""

import requests
import time
import argparse
import sys
import yaml
import json
from pathlib import Path
from typing import List

def toggle_pause(paused: bool, runner_id: int, runner_name: str, headers: dict):
    """Pause or unpause a GitLab runner."""
    data = {
        "paused": "true" if paused else "false"
    }
    GITLAB_API_URL = f"https://gitlab.com/api/v4/runners/{runner_id}"
    response = requests.put(GITLAB_API_URL, headers=headers, data=data)
    if response.ok:
        print(f"Runner {runner_name} with id {runner_id} has been successfully {'paused' if paused else 'unpaused'}.")
    else:
        print(f"Failed to {'pause' if paused else 'unpause'} runner {runner_name} with id {runner_id}: {response.status_code} - {response.text}")

def wait(minutes: int, runner_id: int, runner_name: str, headers: dict):
    """Wait for runner to have no running jobs, cancelling them if timeout."""
    GITLAB_API_URL = f"https://gitlab.com/api/v4/runners/{runner_id}/jobs?status=running"

    if minutes > 0:
        print(f"Starting to wait for {minutes} minute(s)...")
        time_to_reach = time.time() + (minutes * 60)
        start_time = time.time()
        while time.time() < time_to_reach:
            response = requests.get(GITLAB_API_URL, headers=headers)
            jobs = response.json() 
            print(f"Number of running jobs for runner {runner_name} with id {runner_id}: {len(jobs)}")
            if len(jobs) == 0:
                print(f"There are no running jobs for runner {runner_name} with id {runner_id}! Stopping the wait...")
                return
            time.sleep(10)
            print(f"... {(time.time() - start_time) / 60} minute(s) passed waiting for runner {runner_name} with id {runner_id} to have no running jobs...")
        print(f"Timeout reached: Runner {runner_name} with id {runner_id} still has running jobs after {minutes} minutes. Cancelling all its running jobs...")
        # cancel jobs
        response = requests.get(GITLAB_API_URL, headers=headers)
        jobs = response.json()

        for job in jobs:
            project_id = job["pipeline"]["project_id"]
            job_id = job["id"]
            print(f"Cancelling running job with id {job_id} of runner {runner_name} with id {runner_id}...")

            cancel_url = f"https://gitlab.com/api/v4/projects/{project_id}/jobs/{job_id}/cancel"
            cancel_response = requests.post(cancel_url, headers=headers)

            if cancel_response.ok:
                print(f"Cancelled job with id {job_id} of runner {runner_name} with id {runner_id}.")
            else:
                print(f"Failed to cancel job with id {job_id} of runner {runner_name} with id {runner_id}: {cancel_response.status_code} - {cancel_response.text}")

    else:
        print("<=0 minute wait specified, so nothing to do here. Exiting.")

def find_runner_id(runner_name: str, runners_file_paths: List[Path]) -> int:
    """
    Find runner ID by exact name match in one or more runners definition files.
    Returns runner ID or raises SystemExit if not found.
    
    Args:
        runner_name: Name of the runner to find
        runners_file_paths: List of paths to runners definition files
    """
    all_runners = {}  # {node_name: [runners]}
    
    # Load and merge all runners files
    for runners_file_path in runners_file_paths:
        # Validate runners file exists
        if not runners_file_path.exists():
            print(f"Error: Runners file not found: {runners_file_path}")
            sys.exit(1)
        
        # Load runners from the runners file (standardized structure)
        try:
            runners_data = yaml.safe_load(runners_file_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error: Failed to load runners file {runners_file_path}: {e}")
            sys.exit(1)
        
        # Merge runners from this file
        runners_dict = runners_data.get("runners", {})
        for node_name, node_runners in runners_dict.items():
            if node_name not in all_runners:
                all_runners[node_name] = []
            all_runners[node_name].extend(node_runners)
    
    # Search in the merged structure: runners[node_name][runner_index]
    for node_name, node_runners in all_runners.items():
        for runner in node_runners:
            if runner.get("name") == runner_name:
                runner_id = runner.get("id")
                if runner_id:
                    return runner_id
                else:
                    print(f"Error: Runner '{runner_name}' found in cluster definition but has no 'id' field")
                    sys.exit(1)

    # Runner not found - print helpful error
    print(f"Error: Runner '{runner_name}' not found in runners definition")
    print(f"Available runners across {len(runners_file_paths)} file(s):")
    for node_name, node_runners in all_runners.items():
        for runner in node_runners:
            runner_name_in_def = runner.get("name")
            if runner_name_in_def:
                print(f"  - {runner_name_in_def} (node: {node_name})")
    sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pause/unpause GitLab runners")
    parser.add_argument(
        "--runner-name",
        type=str,
        required=True,
        help="Name of the runner (must match exactly with cluster definition)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--pause_wait', action='store_true', help='Pause runner and wait for jobs to finish')
    group.add_argument('--unpause', action='store_true', help='Unpause runner')
    parser.add_argument(
        "--wait_minutes",
        type=int,
        default=30,
        help="Number of minutes to wait for jobs to finish after pausing the runner (default: 30 minutes)",
    )
    parser.add_argument('--token', type=str, required=True, help='GitLab API token for authentication')
    parser.add_argument(
        '--runners-def',
        type=str,
        required=True,
        help='Path to the runners definition file, or JSON array of paths (e.g., cluster_definition/lab_cluster_runners.yaml or \'["file1.yaml", "file2.yaml"]\')'
    )

    args = parser.parse_args()
    runner_name = args.runner_name
    token = args.token
    runners_def_arg = args.runners_def

    # Resolve runners definition path relative to repo root, not current working directory
    # The script may be called from a subdirectory (e.g., local/tf), so we need to
    # find the repo root and resolve the path from there
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent  # gitlab-runner -> infrastructure
    
    # Parse runners_def_arg - can be single path or JSON array of paths
    runners_def_paths = []
    try:
        # Try to parse as JSON array
        parsed = json.loads(runners_def_arg)
        if isinstance(parsed, list):
            runners_def_paths = [Path(p) for p in parsed]
        else:
            # Single path provided as JSON string
            runners_def_paths = [Path(parsed)]
    except (json.JSONDecodeError, TypeError):
        # Not JSON, treat as single path string
        runners_def_paths = [Path(runners_def_arg)]
    
    # Resolve all paths relative to repo root
    resolved_paths = []
    for path in runners_def_paths:
        if not path.is_absolute():
            resolved_path = repo_root / path
        else:
            resolved_path = path
        resolved_paths.append(resolved_path)
    
    # Validate at least one file exists
    existing_paths = [p for p in resolved_paths if p.exists()]
    if not existing_paths:
        print(f"Error: No runners definition files found!")
        print(f"Searched for:")
        for path in resolved_paths:
            print(f"  - {path}")
        print(f"Resolved from repo root: {repo_root}")
        sys.exit(1)
    
    # Find runner ID by exact name match across all files
    runner_id = find_runner_id(runner_name, existing_paths)

    headers = {
        "PRIVATE-TOKEN": token
    }

    if args.pause_wait:
        toggle_pause(True, runner_id, runner_name, headers)
        wait(args.wait_minutes, runner_id, runner_name, headers)
    elif args.unpause:
        toggle_pause(False, runner_id, runner_name, headers)
