import pytest

from middlewared.common.license_reconcile import LicenseReconcileAction, LicenseReconcileDelegate
from middlewared.plugins.truenas.license import TrueNASLicenseService
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import FakeJob, Middleware, fake_service_control


def make_delegate(name, etc_groups, order=0, **attrs):
    return type(
        f"{name}Delegate",
        (LicenseReconcileDelegate,),
        {
            "name": name,
            "etc_groups": etc_groups,
            "order": order,
            **attrs,
        },
    )()


def get_service():
    return create_service(Middleware(), TrueNASLicenseService)


@pytest.mark.asyncio
async def test_duplicate_name_raises():
    service = get_service()
    await service.register_reconcile_delegate(make_delegate("smb", ("smb",)))

    with pytest.raises(ValueError, match="'smb' delegate is already registered"):
        await service.register_reconcile_delegate(make_delegate("smb", ("other",)))


@pytest.mark.asyncio
async def test_duplicate_etc_group_raises_even_with_distinct_name():
    service = get_service()
    await service.register_reconcile_delegate(make_delegate("smb", ("rc", "smb")))

    with pytest.raises(ValueError, match="claims etc group 'rc'"):
        await service.register_reconcile_delegate(make_delegate("nfs", ("nfs", "rc")))

    assert [delegate.name for delegate in await service.reconcile_delegates()] == ["smb"]


@pytest.mark.asyncio
async def test_default_resolve_groups_is_etc_groups():
    middleware = Middleware()
    delegate = make_delegate("smb", ("rc", "smb"))

    assert await delegate.resolve_groups(middleware) == ["rc", "smb"]


def reconcile_service():
    middleware = Middleware()
    rendered = []
    middleware["etc.generate"] = rendered.append
    return create_service(middleware, TrueNASLicenseService), middleware, rendered


@pytest.mark.asyncio
async def test_reconcile_renders_resolved_groups_in_delegate_order():
    service, middleware, rendered = reconcile_service()

    async def resolve_groups(self, middleware):
        return ["scst"]

    await service.register_reconcile_delegate(make_delegate("smb", ("smb",), order=10))
    await service.register_reconcile_delegate(make_delegate("nfs", ("nfsd", "nfs_exports"), order=-5))
    # `etc_groups` is the static superset; only what `resolve_groups` returns gets rendered
    await service.register_reconcile_delegate(
        make_delegate("iscsi", ("scst", "lio"), order=0, resolve_groups=resolve_groups)
    )

    await service.reconcile(FakeJob())

    assert rendered == ["nfsd", "nfs_exports", "scst", "smb"]


@pytest.mark.asyncio
async def test_reconcile_continues_after_a_delegate_raises():
    service, middleware, rendered = reconcile_service()
    job = FakeJob()

    async def resolve_groups(self, middleware):
        raise RuntimeError("this delegate is broken")

    await service.register_reconcile_delegate(make_delegate("nfs", ("nfsd",), order=-5))
    await service.register_reconcile_delegate(
        make_delegate("broken", ("broken",), order=0, resolve_groups=resolve_groups)
    )
    await service.register_reconcile_delegate(make_delegate("smb", ("smb",), order=10))

    await service.reconcile(job)

    assert rendered == ["nfsd", "smb"]
    # The run also has to finish reporting rather than leaving the job stuck at the delegate
    # that blew up.
    assert job.progress[-1] == (100, "License state reconciled")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,service_name",
    [(LicenseReconcileAction.RENDER, None), (LicenseReconcileAction.RELOAD, "cifs")],
)
async def test_reconcile_skips_a_delegate_whose_should_run_is_false(action, service_name):
    """
    The iSCSI and NVMe-oF delegates gate on their target being up, so a delegate that declines
    has to be skipped before its groups are resolved, not merely before a service verb -- which
    is why the RENDER case matters as much as the RELOAD one.
    """
    service, middleware, rendered = reconcile_service()
    control_calls = fake_service_control(middleware)
    resolved = []

    async def should_run(self, middleware):
        return False

    async def resolve_groups(self, middleware):
        resolved.append(self.name)
        return list(self.etc_groups)

    await service.register_reconcile_delegate(
        make_delegate(
            "iscsi",
            ("scst", "lio"),
            should_run=should_run,
            resolve_groups=resolve_groups,
            action=action,
            service=service_name,
        )
    )
    await service.register_reconcile_delegate(make_delegate("nfs", ("nfsd",), order=10))

    await service.reconcile(FakeJob())

    assert rendered == ["nfsd"]
    assert resolved == []
    assert control_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("action", [LicenseReconcileAction.RELOAD, LicenseReconcileAction.RESTART])
async def test_reconcile_issues_service_control_without_ha_propagation(action):
    service, middleware, rendered = reconcile_service()
    control_calls = fake_service_control(middleware)

    await service.register_reconcile_delegate(make_delegate("smb", ("smb",), service="cifs", action=action))

    await service.reconcile(FakeJob())

    # `service.control` renders the service's own `select_etc()`, so the runner renders nothing
    assert rendered == []
    assert control_calls == [(action.value, "cifs", {"ha_propagate": False})]


@pytest.mark.asyncio
async def test_reconcile_names_each_delegate_in_progress():
    service, middleware, rendered = reconcile_service()
    job = FakeJob()

    for name, order in (("smb", 10), ("nfs", -5), ("iscsi", 0)):
        await service.register_reconcile_delegate(make_delegate(name, (name,), order=order))

    await service.reconcile(job)

    assert [description for _, description in job.progress] == [
        "Reconciling nfs",
        "Reconciling iscsi",
        "Reconciling smb",
        "License state reconciled",
    ]
    assert [percent for percent, _ in job.progress] == [0, 33, 66, 100]


@pytest.mark.asyncio
async def test_reconcile_progress_survives_a_service_delegate():
    """
    A RELOAD or RESTART delegate gets a job of its own back from `service.control`, which must not
    displace the reconcile job progress is being reported against.
    """
    service, middleware, rendered = reconcile_service()
    control_job = FakeJob()
    middleware["service.control"] = lambda verb, svc, options=None: control_job
    job = FakeJob()

    await service.register_reconcile_delegate(
        make_delegate("smb", ("smb",), order=-5, service="cifs", action=LicenseReconcileAction.RELOAD)
    )
    await service.register_reconcile_delegate(make_delegate("rc", ("rc",), order=0))

    await service.reconcile(job)

    assert [description for _, description in job.progress] == [
        "Reconciling smb",
        "Reconciling rc",
        "License state reconciled",
    ]
    assert control_job.progress == []
