#!/usr/bin/env python3
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Runner Balancer
Enable/Disable requested runners according to to gitlab load.
"""

import argparse
import json
import logging
from abc import ABC
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from typing import Any, Dict, Generator, List, Optional, Sequence, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    """
    Runner Balancer main
    """
    logging.basicConfig(
        format="%(asctime)s \x1b[32;20m[%(levelname)s]\x1b[0m %(message)s",
        level=logging.DEBUG,
    )

    logging.debug("Runner Balancer Started")

    # Inputs from cmd line
    gitlab_description, data, dryrun = _cmd_line_argument_parser()
    time_ago = datetime.now(UTC) - timedelta(seconds=data.review_period)
    logging.debug("Time reference: %s", time_ago)

    # Gitlab manager creation
    gitlab_manager = GitlabManager(gitlab_description.url, gitlab_description.token)
    group = gitlab_manager.get_group_by_name(gitlab_description.group)

    # List switchable runners
    runner_array = gitlab_manager.get_runners(group, data.switchable_runners)

    # We'll store runners to enable/disable in this list. We'll enable/disable them at the end
    to_enable = []
    to_disable = []

    # Enable alternatives to combination of tags that have pending jobs
    if data.review_period > 0:  # If review period is <= 0 --> Skip enable stage
        enable_runners_to_support_tag_combinations(
            # Dictionary of [tags: array of disabled runners supporting that tag]
            tag_runners_dict=group_runners_by_tag(filter(lambda _runner: not _runner.enabled, runner_array)),
            # List of tags with pending jobs
            tag_array=gitlab_manager.list_pending_tag_combinations(group["id"], time_ago),
            to_enable=to_enable,
        )

    # Disable runners with few jobs in last period.
    if data.min_jobs_per_runner > 0:  # If min jobs <= 0 --> Skip disable stage
        disable_idle_runners(
            runner_jobs_dict={
                runner: gitlab_manager.count_jobs_from_runner(runner, time_ago)
                for runner in filter(lambda _runner: _runner.enabled, runner_array)
            },
            minimum_jobs=data.min_jobs_per_runner,
            to_disable=to_disable,
        )

    # Enable/Disable owned runners according to dryrun flag
    if not dryrun:
        for runner in to_enable:
            gitlab_manager.enable_runner(runner, group, True)
        for runner in to_disable:
            gitlab_manager.enable_runner(runner, group, False)


@dataclass(eq=True, frozen=True)
class _GitlabRunner:
    api_id: int
    tag_list: Tuple[str, ...]
    enabled: bool


@dataclass(frozen=True)
class _AlgorithmInputs:
    review_period: int
    min_jobs_per_runner: int
    switchable_runners: Tuple[int, ...]


def group_runners_by_tag(
    runner_array: Sequence[_GitlabRunner],
) -> Dict[str, List[_GitlabRunner]]:
    """
    Create a dictionary of tag and runners that support that tag.
    The list of runners is sorted according to original order
    """
    tag_runners_dict: Dict[str, List[_GitlabRunner]] = {}

    for runner in runner_array:
        for tag in runner.tag_list:
            if tag not in tag_runners_dict:
                tag_runners_dict[tag] = []
            tag_runners_dict[tag].append(runner)

    return tag_runners_dict


def enable_runners_to_support_tag_combinations(
    tag_runners_dict: Dict[str, List[_GitlabRunner]],
    tag_array: Tuple[Tuple[str, ...], ...],
    to_enable: List[_GitlabRunner],
) -> None:
    """
    Enable Runners to support the list of tag combinations
    """

    logging.debug("= Pending jobs =")

    for tag_combination in tag_array:
        # Check if there is already a runner in the to_enable array that will
        # support this tag combination
        if to_enable:
            already_to_enable = set(to_enable)
            for tag in tag_combination:
                already_to_enable = already_to_enable.intersection(
                    set(
                        tuple(
                            filter(
                                # pylint: disable=cell-var-from-loop
                                lambda _runner: tag in _runner.tag_list,
                                to_enable,
                            )
                        )
                    )
                )
            if already_to_enable:
                logging.debug(
                    "[ == ] Tag '%s' - Future enabled runners that support it %s",
                    ",".join(tag_combination),
                    ",".join(str(_runner.api_id) for _runner in already_to_enable),
                )
                continue

        # Look for a disabled runner that supports the tag
        runner_array_for_tag_combination = set(tag_runners_dict.get(tag_combination[0], []))
        for tag in tag_combination[1:]:
            runner_array_for_tag_combination.intersection(set(tag_runners_dict.get(tag, [])))
        for runner in runner_array_for_tag_combination:
            to_enable.append(runner)
            logging.info(
                "[ >  ] Tag '%s' - To enable runner %s",
                ",".join(tag_combination),
                runner.api_id,
            )
            break
        else:
            if not tag_combination[0]:
                logging.warning(
                    "[ !! ] Tag '%s' - Can't enable more runners",
                    ",".join(tag_combination),
                )


def disable_idle_runners(
    runner_jobs_dict: Dict[_GitlabRunner, int],
    to_disable: List[_GitlabRunner],
    minimum_jobs: int,
) -> None:
    """
    Disable runners with less than `minimum_jobs` in latest `created_ago_sec` seconds
    """

    logging.debug("= Idle Runners =")

    for runner, job_count in runner_jobs_dict.items():
        if job_count < minimum_jobs:
            logging.info(
                "[ || ] Disabling runner %s - %s/%s jobs run since last check.",
                runner.api_id,
                job_count,
                minimum_jobs,
            )
            to_disable.append(runner)
        else:
            logging.debug(
                "[ == ] Keeping runner %s - %s/%s jobs run since last check.",
                runner.api_id,
                job_count,
                minimum_jobs,
            )


##################
## Gitlab Calls ##
##################


class _GitlabApiManager(ABC):  # pylint: disable=too-few-public-methods
    GITLAB_URL = "https://gitlab.com"
    _CI_API_V4_URL_EXTRA = "api/v4"
    _API_TIMEOUT = 10

    def __init__(self, server_url, token) -> None:
        self._server_url = server_url if not server_url.endswith("/") else server_url[::-1]
        self._token = token

    def _call_api(self, query: str, data: Optional[Any], method: str) -> Generator[Any, None, None]:
        while True:
            with suppress(TimeoutError, HTTPError, URLError):
                with urlopen(
                    Request(
                        f"{self._server_url}/{self._CI_API_V4_URL_EXTRA}/{query}",
                        headers={"PRIVATE-TOKEN": self._token},
                        data=data,
                        method=method,
                    ),
                    timeout=self._API_TIMEOUT,
                ) as response:

                    result = json.loads(response.read())
                    if not isinstance(result, list):
                        yield from [result]
                    else:
                        yield from result

                    link_header = response.headers.get("Link")
                    if link_header:
                        next_url = ""
                        for link in link_header.split(","):
                            if 'rel="next"' in link:
                                next_url = link[link.find("<") + 1 : link.find(">")]
                                break

                        if next_url:
                            # Extract query from next_url
                            yield from self._call_api(
                                next_url[
                                    next_url.find(self._CI_API_V4_URL_EXTRA) + len(self._CI_API_V4_URL_EXTRA) + 1 :
                                ],
                                data,
                                method,
                            )
                break

    def _get(self, query: str) -> Generator[Any, None, None]:
        """
        Get a Gitlab API Rest resource
        """
        yield from self._call_api(query, None, "GET")

    def _put(self, query: str, data: Any):
        """
        Get a Gitlab API Rest resource
        """
        tuple(self._call_api(query, data.encode(), "PUT"))


class GitlabManager(_GitlabApiManager):
    """
    Set of operations to achieve in Gitlab
    """

    def get_group_by_name(self, group_name: str) -> Dict:
        """
        Return gitlab group info (Dictionary) by name
        """
        for group_item in self._get(f"groups?name={group_name}"):
            if group_item["full_path"].strip() == group_name:
                for group_obj in self._get(f"groups/{group_item['id']}?with_projects=false"):
                    return dict(group_obj)
        raise ValueError(f"Can't find `{group_name}` group")

    ########
    # Jobs #
    ########

    def list_pending_tag_combinations(self, group_id: int, time_ago: datetime) -> Tuple[Tuple[str, ...], ...]:
        """
        Get all tag combinations from pending or failed (due to the runner) jobs.
        """
        tag_set: Set[Tuple[str, ...]] = set()
        for project in self._get(f"groups/{group_id}/projects?archived=false"):
            if project["jobs_enabled"] or project["builds_access_level"] == "enabled":
                with suppress(HTTPError):
                    # Pending jobs waiting for a runner since `time_ago`
                    for job in self._get(f"projects/{project['id']}/jobs?scope=pending&order_by=id&sort=desc"):
                        created_at = self.cast_gitlab_date(job["created_at"])
                        if created_at < time_ago:
                            for job_detailed in self._get(f"projects/{project['id']}/jobs/{job['id']}"):
                                tag_set.add(tuple(job_detailed["tag_list"] if job_detailed["tag_list"] else [""]))

        for subgroup in self._get(f"groups/{group_id}/subgroups?archived=false"):
            tag_set.update(self.list_pending_tag_combinations(subgroup["id"], time_ago))

        return tuple(sorted(tag_set))

    def count_jobs_from_runner(self, runner: _GitlabRunner, time_ago: datetime) -> int:
        """
        Return a list of jobs run by the specified runner
        """
        count = 0
        if runner.api_id:
            # Count all running jobs
            for job in self._get(f"runners/{runner.api_id}/jobs?status=running"):
                count += 1
            # Count not running jobs in the period
            for status in ("success", "failed", "canceled"):
                for job in self._get(f"runners/{runner.api_id}/jobs?status={status}&order_by=id&sort=desc"):
                    if self.cast_gitlab_date(job["finished_at"]) < time_ago:
                        break
                    count += 1
        return count

    #################
    # Owned Runners #
    #################

    def get_runners(self, group: Dict, switchable_runners: Tuple[int, ...]) -> Tuple[_GitlabRunner, ...]:
        """
        Return a tuple of all owned runners
        """
        runner_list = []
        for runner_id in switchable_runners:
            if runner_id:
                for runner in self._get(f"runners/{runner_id}"):
                    runner_list.append(
                        _GitlabRunner(
                            api_id=runner_id,
                            enabled=not runner["paused"],
                            tag_list=tuple(runner["tag_list"]),
                        )
                    )
            else:
                # Special runner for shared runners
                runner_list.append(
                    _GitlabRunner(
                        api_id=runner_id,
                        enabled=self.are_shared_runners_enabled(group),
                        tag_list=("",),
                    )
                )
        return tuple(runner_list)

    def enable_runner(self, runner: _GitlabRunner, group: Dict, enable: bool) -> None:
        """
        Enable or disable a runner
        """
        if runner.api_id:
            self._put(
                f"runners/{runner.api_id}",
                data=f"paused={str(not enable).lower()}",
            )
        else:
            # Special runner: shared runners
            self.enable_shared_runners(group, enable)

    ##################
    # Shared runners #
    ##################

    def are_shared_runners_enabled(self, group: Dict) -> bool:
        """
        Check if shared runners are enabled or not
        """

        enabled: bool = group["shared_runners_setting"] == "enabled"

        # Go to subgroups
        for subgroup in self._get(f"groups/{group['id']}/subgroups?archived=false"):
            enabled |= self.are_shared_runners_enabled(subgroup)

        # Go to projects
        for project in self._get(f"groups/{group['id']}/projects?archived=false"):
            enabled |= project["shared_runners_enabled"] == "enabled"

        return enabled

    def enable_shared_runners(self, group: Dict, enable: bool) -> None:
        """
        Enable or disable shared runners for the group (and projects in the group)
        """
        # Current group
        # We can't query if a group has shared runners enabled or not
        self._put(
            f"groups/{group['id']}",
            data=f"shared_runners_setting={'enabled' if enable else 'disabled_and_overridable'}",
        )

        # Go to subgroups
        for subgroup in self._get(f"groups/{group['id']}/subgroups?archived=false"):
            self.enable_shared_runners(subgroup, enable)

        # Go to projects
        for project in self._get(f"groups/{group['id']}/projects?archived=false"):
            if project["shared_runners_enabled"] is not enable:
                self._put(
                    f"projects/{project['id']}",
                    data=f"shared_runners_enabled={str(enable).lower()}",
                )

    #########
    # Utils #
    #########

    @staticmethod
    def cast_gitlab_date(gitlab_date: str) -> datetime:
        """
        Convert date in gitlab str format to a python datetime object
        """
        try:
            return datetime.strptime(gitlab_date, "%Y-%m-%dT%H:%M:%S.%f%z")
        except ValueError:
            return datetime.strptime(gitlab_date, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)


##########################
# Command Line Arguments #
##########################


@dataclass(frozen=True)
class _GitlabDescription:
    url: str
    token: str
    group: str


def _cmd_line_argument_parser() -> Tuple[_GitlabDescription, _AlgorithmInputs, bool]:
    parser = argparse.ArgumentParser(description="Gitlab Runner Balancer.")
    parser.add_argument("--url", default=_GitlabApiManager.GITLAB_URL, help="Server URL.")
    parser.add_argument("--token", help="Server token.", required=True)
    parser.add_argument("--group", help="Group.", required=True)
    parser.add_argument(
        "--switchable-runners",
        help="List of runner IDs in order from most priority to less. Separated by spaces.",
        nargs="+",
        default=(),
    )
    parser.add_argument(
        "--min-jobs",
        help="Minimum number of jobs. "
        "A runner will less jobs in period than this value will be paused. "
        "Set to <= 0 to skip Disable stage",
        type=int,
        default=15,
    )
    parser.add_argument(
        "--period",
        help="Time period to review in seconds. " "Set to <= 0 to skip enable stage",
        type=int,
        default=5 * 60,
    )
    parser.add_argument("--dryrun", action="store_true")

    cmd_args = parser.parse_args()
    return (
        _GitlabDescription(url=cmd_args.url, token=cmd_args.token, group=cmd_args.group),
        _AlgorithmInputs(
            review_period=cmd_args.period,
            min_jobs_per_runner=cmd_args.min_jobs,
            switchable_runners=tuple(int(runner_id) for runner_id in cmd_args.switchable_runners),
        ),
        cmd_args.dryrun,
    )


if __name__ == "__main__":
    main()
