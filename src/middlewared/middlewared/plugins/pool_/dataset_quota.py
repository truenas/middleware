from dataclasses import dataclass, field
import errno

from pydantic import ValidationError as PydanticValidationError

from middlewared.api import api_method
from middlewared.api.current import (
    GroupGetGroupObj,
    PoolDatasetGetQuotaArgs,
    PoolDatasetGetQuotaResult,
    PoolDatasetSetQuotaArgs,
    PoolDatasetSetQuotaResult,
    UserGetUserObj,
    ZFSResourceQuery,
    ZFSResourceSetArgsData,
    ZFSResourceUserspaceQuery,
    ZFSResourceUserspaceSetArgsData,
)
from middlewared.plugins.pool_.utils import rekey_validation_error
from middlewared.service import Service
from middlewared.service_exception import ValidationError
from middlewared.utils.filter_list import filter_list
from middlewared.utils.nss import grp, pwd

USERSPACE_SET = 'zfs.resource.userspace.set'
RESOURCE_SET = 'zfs.resource.set'
LEGACY_FIELDS = (('used', 'used_bytes'), ('quota', 'quota'), ('objused', 'obj_used'), ('objquota', 'obj_quota'))


def _xid_name(quota_type, xid):
    try:
        if quota_type == 'USER':
            return pwd.getpwuid(xid, as_dict=True)['pw_name']
        return grp.getgrgid(xid, as_dict=True)['gr_name']
    except Exception:
        return None


def userspace_rows_to_legacy(rows, quota_type):
    """Rows of `zfs.resource.userspace.list` in the shape `pool.dataset.get_quota` returns. A usage or limit of 0 is
    left out, which the UI shows differently from an explicit 0."""
    legacy = []
    for row in rows:
        entry = {'quota_type': quota_type, 'id': row.xid, 'name': _xid_name(quota_type, row.xid)}
        for source, target in LEGACY_FIELDS:
            if value := getattr(row, source):
                entry[target] = value
        legacy.append(entry)
    return legacy


@dataclass(slots=True)
class UserspaceItem:
    type: str
    xid: int
    row: int
    """Index of the first legacy row for this type and id, where an error on the id is reported."""
    limits: dict[str, tuple[int, int]] = field(default_factory=dict)
    """`quota` or `objquota` mapped to its value and the index of the legacy row that last set it."""

    def payload(self):
        return {'type': self.type, 'xid': self.xid} | {name: value for name, (value, _) in self.limits.items()}


@dataclass(slots=True)
class SetQuotaPlan:
    items: list[UserspaceItem] = field(default_factory=list)
    props: dict[str, tuple[int, int]] = field(default_factory=dict)
    """Dataset property mapped to its value and the index of the legacy row that last set it."""


def translate_set_quota(quotas):
    """Translate legacy quota rows whose ids are already resolved into one zfs.resource.userspace item per (type, id)
    and the dataset properties. A later row for the same limit wins."""
    plan = SetQuotaPlan()
    items = {}
    for i, q in enumerate(quotas):
        value = q['quota_value'] or 0
        if q['quota_type'] == 'DATASET':
            plan.props[q['id'].lower()] = (value, i)
            continue

        type_ = 'user' if q['quota_type'].startswith('USER') else 'group'
        if (item := items.get((type_, q['id']))) is None:
            item = items[(type_, q['id'])] = UserspaceItem(type_, q['id'], i)
            plan.items.append(item)
        item.limits['objquota' if q['quota_type'].endswith('OBJ') else 'quota'] = (value, i)
    return plan


def _under(attribute, schema):
    return attribute == schema or attribute.startswith(f'{schema}.')


def rekey_set_quota_error(e, plan):
    """Report an error of the zfs.resource calls `set_quota` makes on the legacy row it came from."""
    attribute = e.attribute or ''
    if attribute in (f'{USERSPACE_SET}.path', RESOURCE_SET, f'{RESOURCE_SET}.path'):
        return ValidationError('dataset', e.errmsg, e.errno)

    prefix = f'{USERSPACE_SET}.quotas.'
    if attribute.startswith(prefix):
        index, _, rest = attribute.removeprefix(prefix).partition('.')
        name = rest.split('.')[0]
        item = plan.items[int(index)]
        if name == 'xid':
            return ValidationError(f'quotas.{item.row}.id', e.errmsg, e.errno)
        if name in item.limits:
            return ValidationError(f'quotas.{item.limits[name][1]}.quota_value', e.errmsg, e.errno)

    prefix = f'{RESOURCE_SET}.properties.'
    if attribute.startswith(prefix) and (name := attribute.removeprefix(prefix).split('.')[0]) in plan.props:
        return ValidationError(f'quotas.{plan.props[name][1]}.quota_value', e.errmsg, e.errno)

    if _under(attribute, USERSPACE_SET) or _under(attribute, RESOURCE_SET):
        return ValidationError('quotas', e.errmsg, e.errno)
    return e


def _build(model, schema, plan, **kwargs):
    try:
        return model(**kwargs)
    except PydanticValidationError as e:
        error = e.errors()[0]
        raise rekey_set_quota_error(
            ValidationError('.'.join([schema, *map(str, error['loc'])]), error['msg'], errno.EINVAL), plan,
        )


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @api_method(
        PoolDatasetGetQuotaArgs,
        PoolDatasetGetQuotaResult,
        roles=['DATASET_READ']
    )
    def get_quota(self, ds, quota_type, filters, options):
        """
        Return a list of the specified ``quota_type`` of quotas on the ZFS dataset ``ds``.
        Supports ``query-filters`` and ``query-options``.

        .. note::

            SMB client requests to set a quota granting no space will result in an on-disk quota of 1 KiB.
        """
        if quota_type == 'PROJECT':
            raise ValidationError('pool.dataset.get_quota', f'Invalid quota type: {quota_type!r}')

        if quota_type == 'DATASET':
            try:
                resources = self.call_sync2(
                    self.s.zfs.resource.list, ZFSResourceQuery(paths=[ds], properties=['quota', 'refquota', 'used']),
                )
            except ValidationError as e:
                raise rekey_validation_error(e, 'zfs.resource.list', 'dataset')
            if not resources:
                raise ValidationError('dataset', f'{ds!r} does not exist.', errno.ENOENT)
            resource = resources[0]
            if resource.type == 'VOLUME':
                raise ValidationError('dataset', f'{ds!r} is a volume; quotas apply to filesystems only.')
            quotas = [{
                'quota_type': quota_type,
                'id': ds,
                'name': ds,
                'quota': resource.properties.quota.value,
                'refquota': resource.properties.refquota.value,
                'used_bytes': resource.properties.used.value,
            }]
        else:
            try:
                rows = self.call_sync2(
                    self.s.zfs.resource.userspace.list,
                    ZFSResourceUserspaceQuery(paths=[ds], types=[quota_type.lower()]),
                )
            except ValidationError as e:
                raise rekey_validation_error(e, 'zfs.resource.userspace.list', 'dataset')
            quotas = userspace_rows_to_legacy(rows, quota_type)

        return filter_list(quotas, filters, options)

    @api_method(
        PoolDatasetSetQuotaArgs,
        PoolDatasetSetQuotaResult,
        roles=['DATASET_WRITE'],
        audit='Pool dataset set quota',
        audit_extended=lambda dataset, quotas=None: dataset,
    )
    def set_quota(self, ds, data):
        """
        Allow users to set multiple quotas simultaneously by submitting a list of quotas.

        ``DATASET`` quotas are set with :method:`zfs.resource.set` and user and group quotas with
        :method:`zfs.resource.userspace.set`. A ``quota_value`` of 0 or null removes the quota.
        """
        quotas = []
        for i, q in enumerate(data):
            if q['quota_type'] == 'DATASET':
                if q['id'] not in ('QUOTA', 'REFQUOTA'):
                    raise ValidationError(
                        f'quotas.{i}.id',
                        'id for quota_type DATASET must be either "QUOTA" or "REFQUOTA"'
                    )
                quotas.append(q)
                continue

            quota_type = q['quota_type'].lower()
            id_type = 'user' if quota_type.startswith('user') else 'group'
            if q['id'].isdigit():
                xid = int(q['id'])
            else:
                try:
                    if id_type == 'user':
                        xid = self.call_sync2(
                            self.s.user.get_user_obj, UserGetUserObj(username=q['id']),
                        ).pw_uid
                    else:
                        xid = self.call_sync2(
                            self.s.group.get_group_obj, GroupGetGroupObj(groupname=q['id']),
                        ).gr_gid
                except Exception:
                    self.logger.debug('Failed to convert %s [%s] to id.', id_type, q['id'], exc_info=True)
                    raise ValidationError(f'quotas.{i}.id', f'{quota_type} {q["id"]} is not valid.')
            if xid == 0:
                raise ValidationError(
                    f'quotas.{i}.id', f'Setting {quota_type} quota on {id_type[0]}id [0] is not permitted'
                )
            quotas.append(q | {'id': xid})

        plan = translate_set_quota(quotas)
        userspace = props = None
        if plan.items:
            userspace = _build(
                ZFSResourceUserspaceSetArgsData, USERSPACE_SET, plan, path=ds,
                quotas=[item.payload() for item in plan.items],
            )
        if plan.props:
            props = _build(
                ZFSResourceSetArgsData, RESOURCE_SET, plan, path=ds,
                properties={name: value for name, (value, _) in plan.props.items()},
            )

        # Dataset limits are accepted on a locked dataset, so the refused userspace write would leave this half applied.
        if userspace is not None and props is not None and self.call_sync2(self.s.zfs.resource.path_is_locked, ds):
            raise ValidationError('dataset', f'{ds!r} is locked. Unlock it first.', errno.EACCES)

        try:
            if props is not None:
                self.call_sync2(self.s.zfs.resource.set, props)
            if userspace is not None:
                self.call_sync2(self.s.zfs.resource.userspace.set, userspace)
        except ValidationError as e:
            raise rekey_set_quota_error(e, plan)
