import ast
from pathlib import Path

import pytest


FUNCTIONS_TO_LOAD = {
    'get_chart_value_format',
    'has_explicit_chart_value_format',
    'is_seconds_based_time_measure',
    'should_convert_seconds_to_hours',
}


def load_time_conversion_helpers():
    source = Path('utils.py').read_text()
    module = ast.parse(source, filename='utils.py')
    selected_nodes = [
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS_TO_LOAD
    ]

    mini_module = ast.Module(body=selected_nodes, type_ignores=[])
    namespace = {}
    exec(compile(mini_module, filename='utils.py', mode='exec'), namespace)
    return namespace


helpers = load_time_conversion_helpers()
get_chart_value_format = helpers['get_chart_value_format']
has_explicit_chart_value_format = helpers['has_explicit_chart_value_format']
should_convert_seconds_to_hours = helpers['should_convert_seconds_to_hours']


@pytest.mark.parametrize(
    ('chart_config', 'measure_name', 'expected'),
    [
        ({'value_format': None}, 'Tempo Gasto', False),
        ({'value_format': 'hours'}, 'Tempo Gasto', True),
        ({'y_axis_format': None}, 'timespent', True),
        ({'y_axis_format': 'hours'}, 'timespent', True),
        ({}, 'timespent', True),
        ({}, 'Tempo Gasto', True),
        ({}, 'story points', False),
    ],
)
def test_should_convert_seconds_to_hours_respects_explicit_preferences(chart_config, measure_name, expected):
    assert should_convert_seconds_to_hours(chart_config, measure_name) is expected


def test_has_explicit_chart_value_format_treats_legacy_y_axis_none_as_unset():
    assert has_explicit_chart_value_format({'y_axis_format': None}) is False
    assert has_explicit_chart_value_format({'y_axis_format': 'hours'}) is True
    assert has_explicit_chart_value_format({'value_format': None}) is True


def test_should_convert_seconds_to_hours_skips_time_in_status_even_if_hours_requested():
    assert should_convert_seconds_to_hours({'value_format': 'hours'}, 'Tempo em Status', True) is False


def test_get_chart_value_format_prioritizes_explicit_value_format_even_when_none():
    chart_config = {'value_format': None, 'y_axis_format': 'hours'}

    assert has_explicit_chart_value_format(chart_config) is True
    assert get_chart_value_format(chart_config) is None
