# -*- coding: utf-8 -*-
"""
    common.utils.swagger
    ~~~~~~~~~~~~~~~~~~~~

    Swagger UI utilities.
"""

from fastapi import FastAPI
from fastapi.routing import APIRoute


def setup_descriptions(app: FastAPI):
    """Setup descriptions for Swagger based on docstrings."""

    for route in app.routes:
        if isinstance(route, APIRoute):
            desc, returns, params = _parse_docstring(route.description)
            route.description = desc
            route.response_description = returns

            dep = route.dependant
            for field in dep.path_params + dep.query_params:
                field.field_info.description = params.get(field.name, "")


def _parse_docstring(rst: str | None) -> tuple[str, str, dict[str, str]]:
    """Parse rST docstring."""

    if not rst or not rst.strip():
        return "", "", {}

    desc, params, returns = [], [], []
    add_to, p_name = desc, None

    for line in rst.splitlines():
        line = line.strip()

        if line.startswith(prefix := ":param "):
            add_to = params
            p_name, p_desc = line[len(prefix):].split(":", 1)
            line = (p_name.strip(), p_desc.lstrip())

        elif line.startswith(prefix := ":return:"):
            add_to = returns
            line = line[len(prefix):].lstrip()

        add_to.append(line)

    d_params = {}
    for p_name, p_desc in params:
        if not (v := d_params.get(p_name, [])):
            d_params[p_name] = v
        v.append(p_desc)

    desc = "\n".join(desc)
    returns = "\n".join(returns).title()
    params = {k: "\n".join(v) for k, v in d_params.items()}

    return desc, returns, params
