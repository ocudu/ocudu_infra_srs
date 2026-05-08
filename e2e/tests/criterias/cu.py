# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
CU alias criteria — one CuCriteria subclass per unique component criteria name.
Delegates to the first matching stub array among cu_cp and cu_up.
"""

import importlib

from retina.launcher.criteria import CuCpCriteria, CuCriteria, CuUpCriteria

# Ensure cu_cp and cu_up subclass lists are populated before generation
importlib.import_module(f"{__package__}.cu_cp")
importlib.import_module(f"{__package__}.cu_up")

# pylint: disable=invalid-name

_seen: set = set()
for _cls in (*CuCpCriteria.subclasses, *CuUpCriteria.subclasses):
    _name = _cls.__qualname__
    if _name not in _seen:
        _seen.add(_name)
        _attrs: dict = {"__doc__": _cls.__doc__, "__module__": __name__}
        if "operator_method" in _cls.__dict__:
            _attrs["operator_method"] = _cls.__dict__["operator_method"]
        type(_name, (CuCriteria,), _attrs)
        # CuCriteria.__init_subclass__ appends each new class to CuCriteria.subclasses
