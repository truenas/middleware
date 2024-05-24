import stat

from .decorators import (
    active_controller,
    ttl_cache,
)
from middlewared.utils.directoryservices.constants import (
    DSStatus, DSType
)
from middlewared.service_exception import CallError
from os import stat_result
from typing import Callable, Union, Optional


class DirectoryServiceInterface:
    """
    Base directory services class. This provides common status-related code
    for directory
    """

    __slots__ = (
        '_ds_type',
        '_name',
        '_status',
        '_datastore_name',
        '_datastore_prefix',
        '_middleware',
        '_nss_module',
        '_has_dns_update',
        '_is_enterprise',
        '_has_sids',
        '_faulted_reason',
        '_etc'
    )

    def __init__(
        self,
        middleware: object,
        ds_type: DSType,
        datastore_name: str,
        datastore_prefix: str,
        nss_module: str,
        is_enterprise: bool,
        etc: list,
        has_sids: Optional[bool] = False,
        has_dns_update: Optional[bool] = False,
    ):
        self._middleware = middleware
        self._ds_type = ds_type
        self._name = DSType(ds_type).value
        self._datastore_name = datastore_name
        self._datastore_prefix = datastore_prefix
        self._nss_module = nss_module
        self._has_dns_update = has_dns_update
        self._has_sids = has_sids
        self._is_enterprise = is_enterprise
        self._status = None
        self._faulted_reason = None
        self._etc = etc

    @property
    def ds_type(self) -> DSType:
        """ Returns the DSType enum member for this directory service """
        return self._ds_type

    @property
    def name(self) -> str:
        """ Returns string representation of DSType """
        return self._name

    def is_enabled(self) -> bool:
        """ Returns whether the directory service is enabled in its config """
        return self.config['enable']

    def _assert_is_active(self) -> None:
        """
        Simple check for whether we're active controller or single node.
        This is called from within the `active_controller` decorator
        """
        if self._is_enterprise:
            if self.call_sync('failover_status') not in ('MASTER', 'SINGLE'):
                raise CallError(
                    'This method may only be called on the active storage controller'
                )

    @property
    def status(self) -> DSStatus:
        """
        Return the current status of the directory service.

        In some edge cases this may block for a potentially significant amount
        of time if middleware has been restarted with a "FAULTED" directory
        service.

        Returns DSStatus type
        """
        if self._status is None:
            if not self.is_enabled():
                return DSStatus.DISABLED

            # We are enabled but have never checked our state
            if not self.call_sync('system.ready'):
                # We may still be starting up. Tell everyone
                # we're still "joining" (until we have successful health check)
                return DSStatus.JOINING

            # Health check should initialze state to something
            # relevant (even if it fails)
            try:
                self.health_check()
            except Exception:
                return DSStatus.FAULTED

            return DSStatus.HEALTHY

        return self._status

    @status.setter
    def status(self, state_in: str):
        try:
            _state = DSStatus[state_in]
        except KeyError:
            raise ValueError(
                f'{state_in}: not a valid directory services state '
                f'choices are: [{x.name for x in DSStatus}]'
            )
        match _state:
            case DSStatus.DISABLED:
                # Avoid caching a DISABLED state to force periodic re-checks
                # of someone surreptitously re-enabling the service via
                # datastore plugin or sqlite commands. Unfortunately, there
                # are some old how-to guides from FreeNAS 9 that advise this.
                self._status = None
            case _:
                self._status = _state

    @property
    def status_msg(self) -> Union[str | None]:
        """
        This method is called when generating summary.
        It returns the reason we're faulted (if we are FAULTED) otherwise
        None
        """
        if self.status == DSStatus.FAULTED:
            return self._faulted_reason

        return None

    @property
    def logger(self) -> Callable:
        return self._middleware.logger

    @property
    def call_sync(self) -> Callable:
        return self._middleware.call_sync

    @property
    def config(self) -> dict:
        """
        Retrieve cached copy of datastore contents for directory service

        Generally the datastore is updated rarely, but queried regularly
        We cache for 60 seconds to mitigate impact of API users polling
        for the directory services status.
        """
        return self._get_config()

    @ttl_cache(ttl=60)
    def _get_config(self) -> None:
        """
        Force an update of the in-memory datastore cache
        """
        conf = self.call_sync('datastore.config', self._datastore_name, {
            'prefix': self._datastore_prefix,
        })
        conf['enumerate'] = not conf.pop('disable_freenas_cache', False)
        return conf

    def update_config(self) -> None:
        self._get_config(ttl_cache_refresh=True)

    def generate_etc(self):
        for etc_file in self._etc:
            self.call_sync('etc.generate', etc_file)

    def _perm_check(
        self,
        st: stat_result,
        expected_mode: int
    ) -> Union[str, None]:
        """
        Perform basic checks that stat security info matches expectations.
        This method is called by during health checks.

        returns a string that will be appended to error messages or None
        type if no errors found
        """
        if st.st_uid != 0:
            return f'file owned by uid {st.st_uid} rather than root.'
        if st.st_gid != 0:
            return f'file owned by gid {st.st_gid} rather than root.'

        if stat.S_IMODE(st.st_mode) != expected_mode:
            return (
                f'file permissions {oct(stat.S_IMODE(st.st_mode))} '
                f'instead of expected value of {oct(expected_mode)}.'
            )

        return None

    def _health_check_impl(self) -> None:
        """
        This method implements the per-directory-service health checks
        """
        raise NotImplementedError

    def health_check(self) -> bool:
        """
        Perform health checks for the directory service. This method gets
        called periodically from the alerting framework to generate health
        alerts. Error recovery is also attempted within the alert source.

        In HA case pass through to master contoller
        """
        if not self.is_enabled():
            self.status = DSStatus.DISABLED.name
            return False
        try:
            if self._is_enterprise:
                match self.call_sync('failover.status'):
                    case 'MASTER' | 'SINGLE':
                        # do health check on this node
                        self._health_check_impl()
                    case 'BACKUP':
                        # get health status from master
                        summary = self.call_sync(
                            'failover.call_remote',
                            'directoryservices.summary'
                        )
                        if summary['status'] == 'FAULTED':
                            self.status = DSStatus.FAULTED.name
                            self._faulted_reason = summary['satus_msg']
                            raise CallError(
                                'Active controller directory service is unhealthy'
                            )
                    case _:
                        # just lie for now and say we're healthy
                        pass
            else:
                self._health_check_impl()
        except Exception as e:
            self.status = DSStatus.FAULTED.name
            raise e from None

        self.status = DSStatus.HEALTHY.name
        return True

    def _summary_impl(self):
        raise NotImplementedError

    def _recover_impl(self):
        raise NotImplementedError

    def recover(self) -> None:
        """
        Attempt to recover our directory service from a FAULTED state.

        This may be a stretch in many cases, but it's better than
        nothing.
        """
        match self.status:
            case DSStatus.JOINING | DSStatus.LEAVING:
                self.logger.debug(
                    "Directory service configuration changes are "
                    "in progress. Skipping recovery attempt."
                )
            case DSStatus.HEALTHY:
                # perhaps we're mistaken
                try:
                    self.health_check()
                    return
                except Exception:
                    # very mistaken
                    pass
            case _:
                # FAULTED
                pass

        return self._recover_impl()

    def activate(self):
        raise NotImplementedError

    def deactivate(self):
        raise NotImplementedError

    @active_controller
    def summary(self):
        return self._summary_impl()

    def is_joined(self) -> bool:
        raise NotImplementedError

    def join(self) -> dict:
        raise NotImplementedError

    def leave(self) -> dict:
        raise NotImplementedError
