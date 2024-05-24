from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.directoryservices.health import (
    KRB5HealthError, IPAHealthCheckFailReason, IPAHealthError,
)
from middlewared.plugins.directoryservices_.all import get_enabled_ds


class IPABindAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "IPA Domain Connection Is Not Healthy"
    text = "IPA health check failed: %(ldaperr)s."


class IPABindAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=10))
    run_on_backup_node = False

    async def check(self):
        ds_obj = await self.middleware.run_in_thread(get_enabled_ds)
        if ds_obj is None or ds_obj.ds_type is not DSType.IPA:
            return

        try:
            await self.middleware.run_in_thread(ds_obj.health_check)
        except KRB5HealthError as e:
            # For now we can simply try to start kerberos
            # to recover from the health issue.
            #
            # This fixes permissions on files (which generates additional
            # error messages regarding type of changes made), gets a
            # fresh kerberos ticket, and sets up a transient job to
            # renew our tickets.
            self.middleware.logger.debug(
                'Attempting to recover kerberos service after health '
                'check failure for the following reason: %s',
                e.errmsg
            )
            try:
                await self.middleware.call('kerberos.start')
            except Exception:
                self.logger.warning('Failed to recover kerberos service.', exc_info=True)

            return Alert(
                IPABindAlertClass,
                {'ldaperr': str(e)},
                key=None
            )
        except IPAHealthError as e:
            # The health check failed do to non-kerberos reasons that we have
            # properly defined. Some of these are recoverable (e.g. regenerating the
            # IPA configuration files), others may require more corrective action
            # (for instance if SSSD totally fails to start)
            match e.reason:
                case IPAHealthCheckFailReason.IPA_NO_CONFIG:
                    self.logger.debug(
                        'IPA configuration file is missing. Attempting to generate new one.'
                    )
                    await self.middleware.call('etc.generate', 'ipa')
                case IPAHealthCheckFailReason.IPA_CONFIG_PERM:
                    self.logger.debug(
                        'IPA configuration file has incorrect permissions. Attempting to fix.'
                    )
                    await self.middleware.call('etc.generate', 'ipa')
                case IPAHealthCheckFailReason.IPA_NO_CACERT:
                    self.logger.debug(
                        'IPA cacert file is missing. Attempting to generate new one.'
                    )
                    await self.middleware.call('etc.generate', 'ipa')
                case IPAHealthCheckFailReason.IPA_CACERT_PERM:
                    self.logger.debug(
                        'IPA cacert file has incorrect permissions. Attempting to fix.'
                    )
                    await self.middleware.call('etc.generate', 'ipa')
                case _:
                    # remaining failure modes don't have clear recovery steps
                    pass

            return Alert(
                IPABindAlertClass,
                {'ldaperr': str(e)},
                key=None
            )
        except Exception as e:
            return Alert(
                IPABindAlertClass,
                {'ldaperr': str(e)},
                key=None
            )
