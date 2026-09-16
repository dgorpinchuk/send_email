from core.template_engine import render, validate_columns, variables_in


def test_variables_in():
    assert variables_in("{{ name }} {{company}} {{ name }}") == ["name", "company"]


def test_render_escapes_html():
    assert render("Hi {{ name }}", {"name": "<Dmitry>"}) == "Hi &lt;Dmitry&gt;"


def test_missing_values():
    assert validate_columns("{{ name }} {{ company }}", ["email", "name"]) == ["company"]


def test_default_unsubscribe_link():
    template = '<a href="{{ unsubscribe_link }}">Unsubscribe</a>'
    expected = '<a href="https://mail.yandex.ru/unsubscribe.html">Unsubscribe</a>'
    assert render(template, {}) == expected
    assert validate_columns(template, ["email", "name"]) == []


def test_explicit_unsubscribe_link_overrides_default():
    template = '<a href="{{ unsubscribe_link }}">Unsubscribe</a>'
    custom = "https://example.com/unsubscribe/123"
    assert render(template, {"unsubscribe_link": custom}) == (
        f'<a href="{custom}">Unsubscribe</a>'
    )
