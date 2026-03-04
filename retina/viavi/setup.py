# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

from os import environ

from setuptools import setup

setup(
    version=environ.get("RETINA_VERSION", "0.0"),
)
