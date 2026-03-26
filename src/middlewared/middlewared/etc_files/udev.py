import pathlib


def render(service, middleware):
    path = pathlib.Path("/etc/udev/rules.d")

    for f in path.iterdir():
        if f.is_file():
            f.unlink()

    tunables = middleware.call_sync2(
        middleware.services.tunable.query, [["type", "=", "UDEV"], ["enabled", "=", True]]
    )
    for tunable in tunables:
        (path / f"{tunable.var}.rules").write_text(tunable.value + "\n")
