# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

# Boost.System has been header-only since Boost 1.69, and since Ubuntu 26.04
# (Boost 1.90) the distribution ships no boost_system CMake component config at
# all -- there is no libboost-system-dev package any more. srsRAN_4G still asks
# for COMPONENTS system whenever UHD is found (a workaround for Ubuntu 18.04),
# so find_package(Boost) fails outright.
#
# This provides the INTERFACE target upstream Boost would generate for a
# header-only library. Point CMake at it with -Dboost_system_DIR=<this dir>.

if(TARGET Boost::system)
  return()
endif()

include(CMakeFindDependencyMacro)
find_dependency(boost_headers ${boost_system_FIND_VERSION} EXACT
                HINTS "${Boost_DIR}/.." "${CMAKE_CURRENT_LIST_DIR}/..")

add_library(Boost::system INTERFACE IMPORTED)
set_target_properties(Boost::system PROPERTIES INTERFACE_LINK_LIBRARIES Boost::headers)
