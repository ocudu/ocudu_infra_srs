#!/usr/bin/env python3

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
This script checks for failed jobs in GitLab pipelines and retries them if they fail due to specific reasons.
"""

import argparse
import logging
import os
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import gitlab
from gitlab.v4.objects import Group, Project, ProjectJob, ProjectPipeline

FAILURE_REASON_ARRAY = (
    "runner_system_failure",
    "job_execution_timeout",
    "stuck_or_timeout_failure",
)

ERROR_ARRAY = (
    "Couldn't connect to server",
    "Could not resolve host",
    "git did not send all necessary objects",
    "smudge filter lfs failed",
    "network is unreachable",
    "Network is unreachable",
    "no longer has a Release file",
    "server misbehaving",
    "Failed to establish a new connection",
    "No report files specified",
    "500 Server Error",
    "The requested URL returned error: 502",
    "The requested URL returned error: 500",
    "maybe run apt-get update or try with --fix-missing",
    "could not connect to unix:///run/buildkit/buildkitd.sock",
    "stop information couldn't be recovered",
    "pod status is failed",
    "TLS connection was non-properly terminated",
    "Illegal instruction",
    "Error cleaning up secrets: resource name may not be empty",
    "(core dumped) gnb --version",
    "You have reached your pull rate limit",
    "Updates for this repository will not be applied",
    "***Exception: Illegal",
    "timed out waiting for pod to start",
    "ErrImagePull",
    "Reason: Gateway Timeout",
    "Pod ephemeral local storage usage exceeds the total limit of containers",
    "Error is not recoverable",
    "Failure when receiving data from the peer",
    "srsgnb/build': No such file or directory",
    "Please call script with target branch name or git hash to perform diff with",
    "the remote end hung up unexpectedly",
    "Caused by SSLError",
    "404  Not Found",
    "Failed to connect to gitlab.com",
    "gnutls_handshake() failed",
    "panic: runtime error: invalid memory address or nil pointer dereference",
    "fetch-pack: invalid index-pack output",
    "fatal: expected flush after ref listing",
    "error: RPC failed; HTTP 500 curl 22",
    "fatal: expected 'acknowledgments'",
    "error: unable to upgrade connection: container not found",
    "connect: connection refused",
    "net/http: TLS handshake timeout",
)

IGNORE_JOB_NAME_ARRAY = (
    "infracheck-k8s",
    "unit coverage",
    "e2e request and config validation",
    "custom e2e",
    "lab-deployer-dryrun",
)


# pylint: disable=too-many-nested-blocks
def _find_failed_jobs_in_pipeline(project: Project, pipeline: ProjectPipeline):
    try:
        for job in pipeline.jobs.list(iterator=True):
            try:
                if job.status == "failed" and job.stage not in ("zmq", "rf") and job.name not in IGNORE_JOB_NAME_ARRAY:
                    job = project.jobs.get(job.id)
                    due_to_my_fail_list = False

                    if job.failure_reason in FAILURE_REASON_ARRAY:
                        due_to_my_fail_list = True
                        supported_error = job.failure_reason

                    if not due_to_my_fail_list:
                        job_log = job.trace().decode("utf-8")
                        if not job_log:  # Empty log
                            due_to_my_fail_list = True
                            supported_error = "Empty log"
                        else:
                            for supported_error in ERROR_ARRAY:
                                if supported_error in job_log:
                                    due_to_my_fail_list = True
                                    break

                    if due_to_my_fail_list:
                        _handle_failed_job(job, supported_error)
            except gitlab.GitlabGetError as err:
                logging.error("Error getting job %s: %s", job.id, err)
    except gitlab.GitlabGetError as err:
        logging.error("Error getting jobs for pipeline %s: %s", pipeline.id, err)


def _handle_failed_job(job: ProjectJob, supported_error: str):
    # Retry the job
    try:
        job.retry()
    except gitlab.GitlabGetError as err:
        logging.error("Error retrying job %s: %s", job.id, err)
    logging.warning(">> '%s' <%s> [%s] - '%s'", job.name, job.web_url, job.pipeline["id"], supported_error)


def _get_child_pipelines(project: Project, job_id):
    job_details = project.jobs.get(job_id)
    pipelines = []
    try:
        pipeline_ids = job_details.attributes["downstream_pipeline_ids"]
        for pipeline_id in pipeline_ids:
            pipeline = project.pipelines.get(pipeline_id)
            pipelines.append(pipeline)
    except gitlab.GitlabGetError as err:
        logging.error("Error getting child pipelines for job %s: %s", job_id, err)
    except KeyError:
        pass
    return pipelines


# pylint: disable=too-many-nested-blocks
def _find_failed_jobs(gl: gitlab.Gitlab, group: Group, from_date: datetime):
    try:

        # Iterate over projects
        for project in group.projects.list(
            archived=False, ci_enabled_first=True, include_subgroups=True, jobs_enabled=True, iterator=True
        ):

            if not project.jobs_enabled:
                continue  # projects with CI enabled

            project = gl.projects.get(project.id)
            logging.debug("Checking project %s from date %s", project.name, from_date)

            # Get running or failed pipelines
            for pipeline in project.pipelines.list(
                iterator=True,
            ):
                if pipeline.updated_at and cast_gitlab_date(pipeline.updated_at) < from_date:
                    logging.debug(
                        "Project %s: Analysis END because pipeline %s: is older than %s",
                        project.name,
                        pipeline.id,
                        from_date,
                    )
                    break  # Older than from_date
                if pipeline.status in ("running", "failed"):
                    logging.debug("Checking pipeline %s", pipeline.web_url)
                    # Find jobs in the main pipeline
                    _find_failed_jobs_in_pipeline(project, pipeline)

                    # Iterate through child pipelines
                    for bridge in pipeline.bridges.list():
                        if (
                            bridge.downstream_pipeline is not None
                            and bridge.downstream_pipeline.get("project_id", "") == project.id
                            and bridge.downstream_pipeline.get("status", "") in ("running", "failed")
                        ):
                            try:
                                _find_failed_jobs_in_pipeline(
                                    project,
                                    project.pipelines.get(bridge.downstream_pipeline["id"]),
                                )
                            except gitlab.GitlabGetError as err:
                                logging.error("Error getting pipeline from bridge %s: %s", bridge, err)

    except Exception as err:  # pylint: disable=broad-except
        logging.error("%s: %s", type(err).__qualname__, str(err))


def cast_gitlab_date(gitlab_date: str) -> datetime:
    """
    Convert date in gitlab str format to a python datetime object
    """
    try:
        return datetime.strptime(gitlab_date, "%Y-%m-%dT%H:%M:%S.%f%z")
    except ValueError:
        return datetime.strptime(gitlab_date, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)


def cmd_line_argument_parser():
    """
    Entrypoint for the scheduler
    """
    parser = argparse.ArgumentParser(description="Show all the jobs that failed in the last N seconds")
    parser.add_argument("--group-id", help="Group ID", type=int, default=11283275)
    parser.add_argument("--gitlab-token", help="Server token.", default=os.getenv("GITLAB_TOKEN"))
    parser.add_argument("--check-before", type=int, help="Check jobs before N seconds", default=60)

    args = parser.parse_args()

    return (
        args.group_id,
        args.gitlab_token,
        datetime.now().replace(tzinfo=ZoneInfo("UTC")) - timedelta(seconds=args.check_before),
    )


def main():
    """
    Entrypoint for the script
    """
    logging.basicConfig(
        format="%(asctime)s \x1b[32;20m[%(levelname)s]\x1b[0m %(message)s",
        level=logging.INFO,
    )

    group_id, gitlab_token, from_date = cmd_line_argument_parser()

    gl = gitlab.Gitlab("https://gitlab.com", private_token=gitlab_token)
    group = gl.groups.get(group_id)

    logging.info("Monitoring failed jobs")

    try:
        _find_failed_jobs(gl, group, from_date)
    except KeyboardInterrupt:
        logging.info("Monitoring failed jobs finished")


if __name__ == "__main__":
    main()

