# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

# BoostConfig.cmake looks up each component with an EXACT version match. Accept
# whatever version it asks for, so this shim needs no edit when the base OS
# bumps Boost. Safe because the target it declares is header-only and carries
# no version-specific ABI.

set(PACKAGE_VERSION "${PACKAGE_FIND_VERSION}")
set(PACKAGE_VERSION_COMPATIBLE TRUE)
set(PACKAGE_VERSION_EXACT TRUE)
