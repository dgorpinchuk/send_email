from core.template_engine import render, validate_columns, variables_in


def test_variables_in():
    assert variables_in("{{ name }} {{company}} {{ name }}") == ["name", "company"]


def test_render_escapes_html():
    assert render("Hi {{ name }}", {"name": "<Dmitry>"}) == "Hi &lt;Dmitry&gt;"


def test_missing_values():
    assert validate_columns("{{ name }} {{ company }}", ["email", "name"]) == ["company"]
