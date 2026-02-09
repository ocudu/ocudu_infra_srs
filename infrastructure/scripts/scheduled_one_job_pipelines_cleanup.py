#!/usr/bin/env python3
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Remove scheduled pipelines with only one job
"""

import argparse
import json
from abc import ABC
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from typing import Any, Dict, Generator, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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

                    if method == "DELETE":
                        break
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

    def _delete(self, query: str):
        """
        Delete a Gitlab API Rest resource
        """
        tuple(self._call_api(query, None, "DELETE"))

    @staticmethod
    def _from_gitlab_date(str_date: str) -> datetime:
        try:
            return datetime.strptime(str_date, "%Y-%m-%dT%H:%M:%S.%f%z")
        except ValueError:
            return datetime.strptime(str_date, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)


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

    def delete_scheduled_one_job_pipelines(
        self,
        group_id: int,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ):
        """
        Delete scheduled pipelines that only had one job
        """

        time_ago = datetime.now(UTC) - timedelta(days=7)

        # Subgroups
        for subgroup in self._get(f"groups/{group_id}/subgroups?archived=false&per_page=100"):
            self.delete_scheduled_one_job_pipelines(subgroup["id"], from_date, to_date)

        # Project
        for project in self._get(f"groups/{group_id}/projects?archived=false&per_page=100"):
            print(project["name"])
            if project["jobs_enabled"] or project["builds_access_level"] == "enabled":
                for pipeline in self._get(
                    f"projects/{project['id']}/pipelines?source=schedule&per_page=25&order_by=id&sort=desc"
                ):
                    jobs = list(self._get(f"projects/{project['id']}/pipelines/{pipeline['id']}/jobs"))
                    if jobs:
                        if (
                            jobs[0]["finished_at"] is not None
                            and self._from_gitlab_date(jobs[0]["finished_at"]) < time_ago
                        ):
                            break
                        if len(jobs) == 1:
                            print(" - " + jobs[0]["name"] + ": " + pipeline["web_url"])
                            self._delete(f"projects/{project['id']}/pipelines/{pipeline['id']}")


@dataclass(frozen=True)
class _GitlabDescription:
    url: str
    token: str
    group: str


def _cmd_line_argument_parser() -> _GitlabDescription:
    parser = argparse.ArgumentParser(description="Gitlab Runner Balancer.")
    parser.add_argument("--url", default=_GitlabApiManager.GITLAB_URL, help="Server URL.")
    parser.add_argument("--token", help="Server token.", required=True)
    parser.add_argument("--group", help="Group.", required=True)

    cmd_args = parser.parse_args()
    return _GitlabDescription(url=cmd_args.url, token=cmd_args.token, group=cmd_args.group)


def main():
    """
    Main
    """
    gitlab_description = _cmd_line_argument_parser()
    gitlab_manager = GitlabManager(gitlab_description.url, gitlab_description.token)
    group = gitlab_manager.get_group_by_name(gitlab_description.group)
    gitlab_manager.delete_scheduled_one_job_pipelines(group["id"])


if __name__ == "__main__":
    main()
