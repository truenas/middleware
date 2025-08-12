from datetime import datetime

import sphinxbootstrap4theme

project = "TrueNAS API $VERSION"
author = "iXsystems, Inc. dba TrueNAS"

# If there is no leading whitespace, it will be
# `Copyright 2024, {author}` for some reason
copyright = f" {datetime.now().year}, {author}"
extensions = [
    "sphinx.ext.duration",
    "sphinx.ext.doctest",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    # "sphinx.ext.intersphinx",
]

# intersphinx_mapping = {
#     "rtd": ("https://docs.readthedocs.io/en/stable/", None),
#     "python": ("https://docs.python.org/3/", None),
#     "sphinx": ("https://www.sphinx-doc.org/en/master/", None),
# }
# intersphinx_disabled_domains = ["std"]

templates_path = ["_templates"]

exclude_patterns = ["_build"]

html_theme = "sphinxbootstrap4theme"
html_theme_path = [sphinxbootstrap4theme.get_path()]

html_theme_options = {
    "navbar_style": "full",
    "navbar_show_pages": False,
    "sidebar_fixed": False,
}

html_static_path = ["_static"]
html_css_files = [
    "style.css",
]
html_js_files = [
    "language_data.js",
    "script.js",
]

html_show_sphinx = False
