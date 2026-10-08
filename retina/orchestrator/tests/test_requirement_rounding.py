# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Unit tests for percentage requirement rounding.
"""

import unittest
from unittest import mock

from retina.orchestrator.requirement import RequirementManager
from retina.orchestrator.reservation import resources
from retina.orchestrator.reservation.resources import _resolve_node_requirements_in_place, round_cpu_quantity


class TestRoundCpuQuantity(unittest.TestCase):
    """Test cases for round_cpu_quantity."""

    def test_fractional_is_unchanged(self):
        """Fractional keeps the scaled value as is."""
        self.assertEqual(round_cpu_quantity("9.9", "fractional"), "9.9")

    def test_truncate(self):
        """Truncate rounds down."""
        self.assertEqual(round_cpu_quantity("15.3", "truncate"), "15")
        self.assertEqual(round_cpu_quantity("9.9", "truncate"), "9")

    def test_round_half_up(self):
        """Round rounds halves up, unlike Python's round()."""
        self.assertEqual(round_cpu_quantity("1.7", "round"), "2")
        self.assertEqual(round_cpu_quantity("4.5", "round"), "5")
        self.assertEqual(round_cpu_quantity("1.4", "round"), "1")

    def test_minimum_one_core(self):
        """Rounding never yields zero cores."""
        self.assertEqual(round_cpu_quantity("0.4", "truncate"), "1")
        self.assertEqual(round_cpu_quantity("0.2", "round"), "1")

    def test_millicores(self):
        """Millicore quantities are converted to cores."""
        self.assertEqual(round_cpu_quantity("11200m", "truncate"), "11")

    def test_invalid_quantity(self):
        """Quantities with other suffixes are rejected."""
        with self.assertRaises(ValueError):
            round_cpu_quantity("4Gi", "truncate")


class TestRequirementManagerRounding(unittest.TestCase):
    """Test cases for rounding parsing."""

    def test_default_is_fractional(self):
        """Without rounding the requirement stays fractional."""
        manager = RequirementManager({"cpu": {"requests": "50%", "limits": "50%"}}, [])
        self.assertEqual(manager.req_list[0].rounding, "fractional")

    def test_invalid_mode(self):
        """Unknown rounding modes are rejected."""
        with self.assertRaises(ValueError):
            RequirementManager({"cpu": {"requests": "50%", "rounding": "ceil"}}, [])

    def test_only_cpu(self):
        """Rounding on non-cpu resources is rejected."""
        with self.assertRaises(ValueError):
            RequirementManager({"memory": {"requests": "50%", "rounding": "truncate"}}, [])


class TestResolveRequirements(unittest.TestCase):
    """Test cases for resolving percentages with rounding."""

    def _resolve(self, config, cpu):
        manager = RequirementManager(config, [])
        with mock.patch.object(
            resources, "get_compute_resources_for_node_from_cluster_info", return_value={"cpu": cpu, "memory": "64Gi"}
        ):
            _resolve_node_requirements_in_place(manager.req_list, mock.Mock(), "node")
        return {req.name: req for req in manager.req_list}

    def test_requests_and_limits_rounded_together(self):
        """Requests and limits are rounded the same way, keeping the pod Guaranteed."""
        reqs = self._resolve({"cpu": {"requests": "90%", "limits": "90%", "rounding": "truncate"}}, 17)
        self.assertEqual((reqs["cpu"].requests, reqs["cpu"].limits), ("15", "15"))

    def test_truncate_plus_round_fits_node(self):
        """Truncate on one container and round on the other never exceed the node."""
        for cores in range(2, 65):
            for pct in range(1, 100):
                # The min-1 floor can overshoot when a share is below one core
                if cores * pct < 100 or cores * (100 - pct) < 100:
                    continue
                ue = self._resolve({"cpu": {"requests": f"{pct}%", "rounding": "truncate"}}, cores)
                mme = self._resolve({"cpu": {"requests": f"{100 - pct}%", "rounding": "round"}}, cores)
                total = int(ue["cpu"].requests) + int(mme["cpu"].requests)
                self.assertLessEqual(total, cores, f"{cores} cores, {pct}%")

    def test_memory_stays_fractional(self):
        """Non-cpu percentages are not rounded."""
        reqs = self._resolve({"memory": {"requests": "50%"}}, 17)
        self.assertEqual(reqs["memory"].requests, "32Gi")


if __name__ == "__main__":
    unittest.main()
