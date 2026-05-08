# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
gNB alias criteria — one GnbCriteria subclass per unique component criteria name.
Delegates to the first matching stub array among cu_cp, cu_up, du (deduplicated).
"""

import importlib

from retina.launcher.criteria import CuCpCriteria, CuUpCriteria, DuCriteria, GnbCriteria

# Ensure cu_cp, cu_up and du subclass lists are populated before generation
importlib.import_module(f"{__package__}.cu_cp")
importlib.import_module(f"{__package__}.cu_up")
importlib.import_module(f"{__package__}.du")

# pylint: disable=invalid-name

_seen: set = set()
for _cls in (*CuCpCriteria.subclasses, *CuUpCriteria.subclasses, *DuCriteria.subclasses):
    _name = _cls.__qualname__
    if _name not in _seen:
        _seen.add(_name)
        _attrs: dict = {"__doc__": _cls.__doc__, "__module__": __name__}
        if "operator_method" in _cls.__dict__:
            _attrs["operator_method"] = _cls.__dict__["operator_method"]
        type(_name, (GnbCriteria,), _attrs)
        # GnbCriteria.__init_subclass__ appends each new class to GnbCriteria.subclasses
