import re

import pytest
from functions import http_get

from middlewared.test.integration.utils import url

RE_MAIN_SCRIPT = re.compile(r'<script src="(main[.-].+\.js)" type="module">')


@pytest.mark.parametrize("path", ["/", "/ui", "/ui/", "/ui/index.html", "/ui/sessions/signin"])
def test_index_html(path):
    r = http_get(url() + path, timeout=10)

    assert r.status_code == 200

    assert "Strict-Transport-Security" in r.headers

    # FIXME: There is no easy way to fix this for index.html, but since this path never appears anywhere,
    # we can probably ignore this for now
    if path != "/ui/index.html":
        assert r.headers["Cache-Control"] == "no-store, no-cache, must-revalidate, max-age=0"

    assert RE_MAIN_SCRIPT.search(r.text)


def test_assets():
    r = http_get(url(), timeout=10)

    m = RE_MAIN_SCRIPT.search(r.text)
    r = http_get(url() + f"/ui/{m.group(1)}")

    assert "Strict-Transport-Security" in r.headers

    assert r.headers["Cache-Control"] == "must-revalidate"
