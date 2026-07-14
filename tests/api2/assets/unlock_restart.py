from middlewared.test.integration.utils import call, ssh


PASSPHRASE = "12345678"


def encryption_props():
    return {
        "encryption_options": {"generate_key": False, "passphrase": PASSPHRASE},
        "encryption": True,
        "inherit_encryption": False,
    }


def unlock(dataset):
    call(
        "pool.dataset.unlock",
        dataset,
        {"datasets": [{"name": dataset, "passphrase": PASSPHRASE}]},
        job=True,
    )


def marker_mock(path):
    # A mock body that just creates `path`, so a test can assert the mocked method was called.
    # `*args` absorbs the `job` argument too, so this works for job and non-job methods alike.
    return f"""
        def mock(self, *args):
            open("{path}", "w").close()
    """


def model_mock(expression):
    # `vm` and `container` are typesafe namespaces: their methods hand back API model instances, and
    # a dict returned by a mock is only converted to a model one level deep -- nested `devices` and
    # `status` would stay dicts and fail on attribute access. So `expression`, a single line of
    # Python building the models, is evaluated inside the mock body, which middleware execs
    # server-side where the models are importable.
    return f"""
        from middlewared.api.current import *

        def mock(self, *args):
            return {expression}
    """


def assert_started_only_after_all_deps_unlocked(marker, first_dataset, second_dataset):
    # Unlocking `first_dataset` alone must NOT start the workload -- a dependency on
    # `second_dataset` is still locked -- so it is started only once `second_dataset` is unlocked.
    ssh(f"rm -f {marker}")
    unlock(first_dataset)
    ssh(f"test ! -f {marker}")
    unlock(second_dataset)
    call("filesystem.stat", marker)
