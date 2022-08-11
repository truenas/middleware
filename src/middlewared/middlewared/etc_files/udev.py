import pathlib


def render(service, middleware):
    path = pathlib.Path("/etc/udev/rules.d")

    for f in path.iterdir():
        if f.is_file():
            f.unlink()

    for tunable in middleware.call_sync("tunable.query", [["type", "=", "UDEV"], ["enabled", "=", True]]):
        (path / f"{tunable['var']}.rules").write_text(tunable["value"] + "\n")
