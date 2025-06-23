import pathlib
import sys

# put spess on the path
sys.path.insert(0, str(pathlib.Path('..').resolve()))

# at large metadata
project = 'spess'
copyright = '2025, Aaron Griffith'
author = 'Aaron Griffith'

# sphinx extensions to use
extensions = [
    'sphinx.ext.autodoc',
]

# templates and theme
#templates_path = ['_templates']
#exclude_patterns = []
html_theme = 'sphinx_rtd_theme'
#html_static_path = ['_static']

# autodoc config
autodoc_class_signature = 'separated'
autodoc_type_aliases = {
    # do not expand the Json type alias
    'Json': 'spess._json.Json',
}
