# Fool setuptools to prevent
#     error: Namespace package problem: middlewared is a namespace package, but its
#     __init__.py does not call declare_namespace()! Please fix it.
#     (See the setuptools manual under "Namespace Packages" for details.)
# when running setup_test.py
# (it checks for presence of declare_namespace in __init__.py so the above paragraph
# alone does the job)

import os
from .fake_env import setup_fake_middleware_env


if os.environ.get("FAKE_ENV"):
    setup_fake_middleware_env()
