import pytest

from middlewared.plugins.container.utils import build_etc_hosts_content

STANDARD_HOSTS = [
    "127.0.0.1\tlocalhost\n",
    "127.0.1.1\tLXC_NAME\n",
    "::1\t\tlocalhost ip6-localhost ip6-loopback\n",
    "ff02::1\t\tip6-allnodes\n",
    "ff02::2\t\tip6-allrouters\n",
]


@pytest.mark.parametrize("existing_lines,name,expected", [
    # Replace LXC_NAME placeholder
    (
        STANDARD_HOSTS,
        "mycontainer",
        [
            "127.0.0.1\tlocalhost\n",
            "127.0.1.1\tmycontainer\n",
            "::1\t\tlocalhost ip6-localhost ip6-loopback\n",
            "ff02::1\t\tip6-allnodes\n",
            "ff02::2\t\tip6-allrouters\n",
        ],
    ),
    # Rename: old name -> new name
    (
        [
            "127.0.0.1\tlocalhost\n",
            "127.0.1.1\told-name\n",
        ],
        "new-name",
        [
            "127.0.0.1\tlocalhost\n",
            "127.0.1.1\tnew-name\n",
        ],
    ),
    # No 127.0.1.1 line — append
    (
        [
            "127.0.0.1\tlocalhost\n",
            "::1\t\tlocalhost\n",
        ],
        "mycontainer",
        [
            "127.0.0.1\tlocalhost\n",
            "::1\t\tlocalhost\n",
            "127.0.1.1\tmycontainer\n",
        ],
    ),
    # Empty file
    (
        [],
        "mycontainer",
        [
            "127.0.1.1\tmycontainer\n",
        ],
    ),
    # Idempotent — name already correct
    (
        [
            "127.0.0.1\tlocalhost\n",
            "127.0.1.1\tmycontainer\n",
        ],
        "mycontainer",
        [
            "127.0.0.1\tlocalhost\n",
            "127.0.1.1\tmycontainer\n",
        ],
    ),
    # User-added entries on other lines preserved
    (
        [
            "127.0.0.1\tlocalhost\n",
            "127.0.1.1\tLXC_NAME\n",
            "10.0.0.5\tdbserver\n",
            "192.168.1.100\tfileserver\n",
        ],
        "mycontainer",
        [
            "127.0.0.1\tlocalhost\n",
            "127.0.1.1\tmycontainer\n",
            "10.0.0.5\tdbserver\n",
            "192.168.1.100\tfileserver\n",
        ],
    ),
    # 127.0.1.1 with multiple aliases — still replaced entirely
    (
        [
            "127.0.0.1\tlocalhost\n",
            "127.0.1.1\tLXC_NAME LXC_NAME.localdomain\n",
        ],
        "mycontainer",
        [
            "127.0.0.1\tlocalhost\n",
            "127.0.1.1\tmycontainer\n",
        ],
    ),
    # Blank lines preserved
    (
        [
            "127.0.0.1\tlocalhost\n",
            "\n",
            "127.0.1.1\tLXC_NAME\n",
            "\n",
        ],
        "mycontainer",
        [
            "127.0.0.1\tlocalhost\n",
            "\n",
            "127.0.1.1\tmycontainer\n",
            "\n",
        ],
    ),
])
def test__build_etc_hosts_content(existing_lines, name, expected):
    assert build_etc_hosts_content(existing_lines, name) == expected
