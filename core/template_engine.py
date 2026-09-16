"""Small, deterministic {{ variable }} template engine."""

import re
from html import escape

VARIABLE_RE = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")


def variables_in(template: str) -> list[str]:
    """Return unique variables in first-seen order."""
    return list(dict.fromkeys(VARIABLE_RE.findall(template)))


def render(template: str, values: dict[str, object]) -> str:
    """Render a template, HTML-escaping values to avoid accidental markup injection."""
    variables = variables_in(template)
    missing = [name for name in variables if name not in values]
    if missing:
        raise ValueError(f"Missing template values: {', '.join(missing)}")

    def replace(match: re.Match[str]) -> str:
        return escape(str(values[match.group(1)]), quote=True)

    return VARIABLE_RE.sub(replace, template)


def validate_columns(template: str, columns: list[str]) -> list[str]:
    """Return template variables that are not present in the input columns."""
    column_set = {c.strip() for c in columns if c.strip()}
    return [name for name in variables_in(template) if name not in column_set]
