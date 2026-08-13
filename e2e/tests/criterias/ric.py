# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Near-RT RIC pass/fail criteria definitions.
"""

import operator

from google.protobuf.empty_pb2 import Empty
from retina.launcher.criteria import RicCriteria

# pylint: disable=invalid-name,missing-function-docstring,too-few-public-methods


class nof_connected_agents_ge(RicCriteria):
    """E2 Agents Connected"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).ric.nof_connected_agents for s in self._stub_array)


class nof_connected_xapps_ge(RicCriteria):
    """xApps Connected"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).ric.nof_connected_xapps for s in self._stub_array)


class nof_subscription_reqs_ge(RicCriteria):
    """E2 Subscription Requests"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).ric.nof_subscription_reqs for s in self._stub_array)


class nof_unanswered_subscriptions_eq(RicCriteria):
    """E2 Subscriptions Without Response"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(
            s.GetMetrics(Empty()).ric.nof_subscription_reqs - s.GetMetrics(Empty()).ric.nof_subscription_reps
            for s in self._stub_array
        )


class nof_ric_indication_ge(RicCriteria):
    """E2 Indication Messages"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).ric.nof_ric_indication for s in self._stub_array)


class nof_control_reqs_ge(RicCriteria):
    """E2 Control Requests"""

    operator_method = operator.ge

    def callback(self) -> int:
        return sum(s.GetMetrics(Empty()).ric.nof_control_reqs for s in self._stub_array)


class nof_unanswered_controls_eq(RicCriteria):
    """E2 Control Requests Without Acknowledgement"""

    operator_method = operator.eq

    def callback(self) -> int:
        return sum(
            s.GetMetrics(Empty()).ric.nof_control_reqs - s.GetMetrics(Empty()).ric.nof_control_reps
            for s in self._stub_array
        )
