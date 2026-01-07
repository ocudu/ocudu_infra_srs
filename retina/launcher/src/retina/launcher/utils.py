#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Non-fixtures (function, classes, etc.) available to use from tests
"""

from contextlib import suppress
from typing import Collection, Optional, Union

import pytest
from _pytest.mark.structures import ParameterSet

from retina.launcher.artifacts import RetinaTestData


def param(
    *values: object,
    marks: Union[pytest.MarkDecorator, Collection[Union[pytest.MarkDecorator, pytest.Mark]]] = (),
    id: Optional[str] = None,  # pylint: disable=redefined-builtin
) -> ParameterSet:
    """Specify a parameter in `pytest.mark.parametrize`_ calls or
    :ref:`parametrized fixtures <fixture-parametrize-marks>`.

    .. code-block:: python

        @pytest.mark.parametrize(
            "test_input,expected",
            [
                ("3+5", 8),
                param("6*9", 42, marks=pytest.mark.xfail),
            ],
        )
        def test_eval(test_input, expected):
            assert eval(test_input) == expected

    :param values: Variable args of the values of the parameter set, in order.
    :param marks: A single mark or a list of marks to be applied to this parameter set.
    :param id: The id to attribute to this parameter set. It will be formatted using id % values syntax
    """
    if id is not None:
        with suppress(TypeError):
            id = id % values
    return pytest.param(*values, marks=marks, id=id)


def configure_artifacts(
    retina_data: RetinaTestData,
    always_download_artifacts: bool = True,
) -> None:
    """
    Configure artifacts features
    """
    retina_data.download_artifacts |= always_download_artifacts
