# Copyright 2010 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

from django.conf.urls import url
from freenasUI.system.forms import (
    ManualUpdateWizard,
    ManualUpdateTemporaryLocationForm,
    ManualUpdateUploadForm,
    InitialWizard,
    InitialWizardConfirmForm,
    InitialWizardDSForm,
    InitialWizardSettingsForm,
    InitialWizardShareFormSet,
    InitialWizardSystemForm,
    InitialWizardVolumeForm,
    InitialWizardVolumeImportForm
)

from .views import (
    home, initialwizard_progress, reboot, reboot_dialog, reboot_run, shutdown,
    shutdown_dialog, shutdown_run, reporting, system_info, bootenv_activate,
    manualupdate_progress, bootenv_add, bootenv_pool_attach, bootenv_pool_detach,
    bootenv_pool_replace, bootenv_scrub, bootenv_scrub_interval, bootenv_deletebulk,
    bootenv_deletebulk_progress, bootenv_delete, bootenv_rename, bootenv_keep,
    bootenv_unkeep, bootenv_datagrid, bootenv_datagrid_structure,
    bootenv_datagrid_actions, config_restore, config_save, config_download,
    config_upload, debug,
    debug_download, backup, backup_progress, backup_abort, varlogmessages,
    top, testmail, directory_browser, file_browser, restart_httpd, reload_httpd,
    restart_httpd_all, terminal, terminal_paste, update_index, update_apply,
    update_check, update_save, update_progress, update_verify, verify_progress,
    CA_import, CA_create_internal, CA_create_intermediate, CA_edit,
    CA_export_certificate, CA_export_privatekey, CA_info,
    certificate_import, certificate_create_internal, certificate_edit, CSR_edit,
    certificate_create_CSR, certificate_export_certificate, certificate_export_privatekey,
    certificate_export_certificate_and_privatekey, certificate_info,
)


urlpatterns = [
    url(r'^$', home, name="system_home"),
    url(r'^wizard/$', InitialWizard.as_view(
        [
            ('settings', InitialWizardSettingsForm),
            ('import', InitialWizardVolumeImportForm),
            ('volume', InitialWizardVolumeForm),
            ('ds', InitialWizardDSForm),
            ('shares', InitialWizardShareFormSet),
            ('system', InitialWizardSystemForm),
            ('confirm', InitialWizardConfirmForm),
        ],
        condition_dict={
            'ds': InitialWizardDSForm.show_condition,
            'import': InitialWizardVolumeImportForm.show_condition,
            'volume': InitialWizardVolumeForm.show_condition,
        },
    ), name='system_initialwizard'),
    url(r'^wizard/progress/$', initialwizard_progress, name="system_initialwizard_progress"),
    url(r'^reboot/$', reboot, name="system_reboot"),
    url(r'^reboot/dialog/$', reboot_dialog, name="system_reboot_dialog"),
    url(r'^reboot/run/$', reboot_run, name="system_reboot_run"),
    url(r'^shutdown/$', shutdown, name="system_shutdown"),
    url(r'^shutdown/dialog/$', shutdown_dialog, name="system_shutdown_dialog"),
    url(r'^shutdown/run/$', shutdown_run, name="system_shutdown_run"),
    url(r'^reporting/$', reporting, name="system_reporting"),
    url(r'^info/$', system_info, name="system_info"),
    url(r'^manualupdate/$', ManualUpdateWizard.as_view(
        [ManualUpdateTemporaryLocationForm, ManualUpdateUploadForm]
    ), name='system_manualupdate'),
    url(r'^manualupdate/progress/$', manualupdate_progress, name="system_manualupdate_progress"),
    url(r'^bootenv/activate/(?P<name>[^/]+)/$', bootenv_activate, name='system_bootenv_activate'),
    url(r'^bootenv/add/$', bootenv_add, name='system_bootenv_add'),
    url(r'^bootenv/add/(?P<source>[^/]+)/$', bootenv_add, name='system_bootenv_add'),
    url(r'^bootenv/pool/attach/$', bootenv_pool_attach, name='system_bootenv_pool_attach'),
    url(r'^bootenv/pool/detach/(?P<label>.+)/$', bootenv_pool_detach, name='system_bootenv_pool_detach'),
    url(r'^bootenv/pool/replace/(?P<label>.+)/$', bootenv_pool_replace, name='system_bootenv_pool_replace'),
    url(r'^bootenv/scrub/$', bootenv_scrub, name='system_bootenv_scrub'),
    url(r'^bootenv/scrub/interval/$', bootenv_scrub_interval, name='system_bootenv_scrub_interval'),
    url(r'^bootenv/bulk-delete/$', bootenv_deletebulk, name='system_bootenv_deletebulk'),
    url(r'^bootenv/bulk-delete/progress/$', bootenv_deletebulk_progress, name='system_bootenv_deletebulk_progress'),
    url(r'^bootenv/delete/(?P<name>[^/]+)/$', bootenv_delete, name='system_bootenv_delete'),
    url(r'^bootenv/rename/(?P<name>[^/]+)/$', bootenv_rename, name='system_bootenv_rename'),
    url(r'^bootenv/keep/(?P<name>[^/]+)/$', bootenv_keep, name='system_bootenv_keep'),
    url(r'^bootenv/unkeep/(?P<name>[^/]+)/$', bootenv_unkeep, name='system_bootenv_unkeep'),
    url(r'^bootenv/datagrid/$', bootenv_datagrid, name='system_bootenv_datagrid'),
    url(r'^bootenv/datagrid/structure/$', bootenv_datagrid_structure, name='system_bootenv_datagrid_structure'),
    url(r'^bootenv/datagrid/actions/$', bootenv_datagrid_actions, name='system_bootenv_datagrid_actions'),
    url(r'^config/restore/$', config_restore, name='system_configrestore'),
    url(r'^config/save/$', config_save, name='system_configsave'),
    url(r'^config/download/$', config_download, name='system_configdownload'),
    url(r'^config/upload/$', config_upload, name='system_configupload'),
    url(r'^debug/$', debug, name='system_debug'),
    url(r'^debug/download/$', debug_download, name='system_debug_download'),
    url(r'^backup/$', backup, name='system_backup'),
    url(r'^backup/progress$', backup_progress, name='system_backup_progress'),
    url(r'^backup/abort$', backup_abort, name='system_backup_abort'),
    url(r'^varlogmessages/(?P<lines>\d+)?/?$', varlogmessages, name="system_messages"),
    url(r'^top/', top, name="system_top"),
    url(r'^test-mail/$', testmail, name="system_testmail"),
    url(r'^lsdir/(?P<path>.*)$', directory_browser, name="system_dirbrowser"),
    url(r'^lsfiles/(?P<path>.*)$', file_browser, name="system_filebrowser"),
    url(r'^restart-httpd/$', restart_httpd, name="system_restart_httpd"),
    url(r'^reload-httpd/$', reload_httpd, name="system_reload_httpd"),
    url(r'^restart-httpd-all/$', restart_httpd_all, name="system_restart_httpd_all"),
    url(r'^terminal/$', terminal, name="system_terminal"),
    url(r'^terminal/paste/$', terminal_paste, name="system_terminal_paste"),
    url(r'^update-index/$', update_index, name="system_update_index"),
    url(r'^update/apply/$', update_apply, name="system_update_apply"),
    url(r'^update/check/$', update_check, name="system_update_check"),
    url(r'^update/save/$', update_save, name="system_update_save"),
    url(r'^update/progress/$', update_progress, name="system_update_progress"),
    url(r'^update/verify/$', update_verify, name="system_update_verify"),
    url(r'^update/verify_progress/$', verify_progress, name="system_verify_progress"),
    url(r'^CA/import/$', CA_import, name="CA_import"),
    url(r'^CA/create/internal/$', CA_create_internal, name="CA_create_internal"),
    url(r'^CA/create/intermediate/$', CA_create_intermediate, name="CA_create_intermediate"),
    url(r'^CA/edit/(?P<id>\d+)/$', CA_edit, name="CA_edit"),
    url(r'^CA/export/certificate/(?P<id>\d+)/$', CA_export_certificate, name="CA_export_certificate"),
    url(r'^CA/export/privatekey/(?P<id>\d+)/$', CA_export_privatekey, name="CA_export_privatekey"),
    url(r'^CA/info/(?P<id>\d+)/$', CA_info, name="CA_info"),
    url(r'^certificate/import/$', certificate_import, name="certificate_import"),
    url(r'^certificate/create/internal/$', certificate_create_internal, name="certificate_create_internal"),
    url(r'^certificate/edit/(?P<id>\d+)/$', certificate_edit, name="certificate_edit"),
    url(r'^certificate/CSR/edit/(?P<id>\d+)/$', CSR_edit, name="CSR_edit"),
    url(r'^certificate/create/CSR/$', certificate_create_CSR, name="certificate_create_CSR"),
    url(r'^certificate/export/certificate/(?P<id>\d+)$', certificate_export_certificate, name="certificate_export_certificate"),
    url(r'^certificate/export/privatekey/(?P<id>\d+)$', certificate_export_privatekey, name="certificate_export_privatekey"),
    url(r'^certificate/export/certificate/privatekey/(?P<id>\d+)$', certificate_export_certificate_and_privatekey, name="certificate_export_certificate_and_privatekey"),
    url(r'^certificate/info/(?P<id>\d+)/$', certificate_info, name="certificate_info"),
]
