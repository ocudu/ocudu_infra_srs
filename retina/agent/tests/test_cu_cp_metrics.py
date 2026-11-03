# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Unit tests for the CU-CP JSON metrics analyzer.
"""

import unittest

from retina.agent.features.json_metrics.cu_cp_metrics import CuCpMetricsAnalyzer


def _cu_cp_record(mt_access_per_du: dict) -> dict:
    return {
        "cu-cp": {
            "rrcs": {
                "du": [
                    {
                        "gnb_du_id": du_id,
                        "rrc_connection_establishment": {
                            "successful_rrc_connection_establishments": {"mo_sig": 7, "mt_access": mt_access}
                        },
                    }
                    for du_id, mt_access in mt_access_per_du.items()
                ]
            }
        }
    }


class TestCuCpMetricsAnalyzer(unittest.TestCase):
    """CuCpMetricsAnalyzer: MT-Access RRC connection establishments."""

    def setUp(self):
        self.a = CuCpMetricsAnalyzer()

    def test_no_cu_cp_records_reports_zero(self):
        self.a.process({"cells": []})
        self.assertEqual(self.a.report().cu_cp.nof_mt_access_rrc_connection_establishments, 0)

    def test_cumulative_counter_keeps_last_report(self):
        for mt_access in (0, 3, 10):
            self.a.process(_cu_cp_record({0: mt_access}))
        self.assertEqual(self.a.report().cu_cp.nof_mt_access_rrc_connection_establishments, 10)

    def test_records_without_cu_cp_do_not_reset_counter(self):
        self.a.process(_cu_cp_record({0: 5}))
        self.a.process({"cells": []})
        self.assertEqual(self.a.report().cu_cp.nof_mt_access_rrc_connection_establishments, 5)

    def test_multiple_dus_summed(self):
        self.a.process(_cu_cp_record({0: 4, 1: 6}))
        self.a.process(_cu_cp_record({0: 5}))
        self.assertEqual(self.a.report().cu_cp.nof_mt_access_rrc_connection_establishments, 11)


if __name__ == "__main__":
    unittest.main()
