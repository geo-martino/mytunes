# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
from datetime import datetime
from pathlib import Path

from mytunes import MODULE_ROOT, PROGRAM_OWNER_NAME, PROGRAM_OWNER_USER, PROGRAM_NAME


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = PROGRAM_NAME
copyright = f"{datetime.now().year}, {PROGRAM_OWNER_NAME}"
author = PROGRAM_OWNER_NAME


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

# noinspection SpellCheckingInspection
extensions = [
    "sphinx_rtd_theme",
    "sphinx.ext.autodoc",
    "sphinx.ext.graphviz",
    "sphinx.ext.inheritance_diagram",
    "sphinx_autodoc_typehints",
    "autodocsumm",
    "sphinxext.opengraph",
    "sphinx_new_tab_link",
]
# noinspection SpellCheckingInspection
autodoc_member_order = "bysource"
# noinspection SpellCheckingInspection
autodoc_default_options = {
    "autosummary": True,
    "members": True,
    "undoc-members": False,
    "inherited-members": False,
    "special-members": False,
    "show-inheritance": True,
    # "member-order": "bysource",
}
typehints_defaults = "braces"
typehints_use_rtype = False

templates_path = ["_templates"]
exclude_patterns = ["_build", "reference/mytunes.rst"]

suppress_warnings = [
    "sphinx_autodoc_typehints.forward_reference",
    # TODO: 'sphinx_autodoc_typehints.forward_reference' not yet supported.
    #  See https://github.com/tox-dev/sphinx-autodoc-typehints/pull/433/files
    "sphinx.ext.inheritance_diagram",
    # TODO: Suppress 'WARNING: No classes found for inheritance diagram'
]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_static_path = ["_static"]
html_title = project

html_theme = "sphinx_rtd_theme"
html_theme_options = dict(
    collapse_navigation=False,
    sticky_navigation=True,
    navigation_depth=-1,
    includehidden=True,
    titles_only=False,
)
# html_logo = "_images/mytunes-logo.png"
html_css_files = [
    "style.css",
]
html_context = dict(
    display_github=True,
    github_user=PROGRAM_OWNER_USER,
    github_repo=MODULE_ROOT,
    github_version="HEAD",
    conf_py_path=f"/{Path(__file__).parent.name}/",
)


# -- OpenGraph configuration --------------------------------------------------

ogp_site_url = f"https://{PROGRAM_OWNER_USER}.github.io/{PROGRAM_NAME.lower()}/"


# -- GraphViz configuration --------------------------------------------------
# https://graphviz.org/doc/info/attrs.html

graphviz_output_format = "svg"
inheritance_graph_attrs = dict(
    rankdir="TB", size='""', fontsize=10, ratio="auto", center="true", style="solid"
)
inheritance_node_attrs = dict(shape="ellipse", fontsize=10, fontname="monospace")
