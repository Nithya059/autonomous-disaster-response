# app package root — intentionally empty.
# Presence of this file makes `app` a Python package so that
# `from app.config import get_settings` and all other absolute
# imports resolve correctly when running from the backend/ directory,
# as configured by pyproject.toml [tool.pytest.ini_options] pythonpath.
