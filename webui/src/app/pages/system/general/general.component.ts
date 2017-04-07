import { Component } from '@angular/core';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { RestService } from '../../../services/rest.service';

@Component({
  selector: 'app-general',
  template: `<entity-config [conf]="this"></entity-config>`
})
export class GeneralComponent {

  protected resource_name: string = 'system/settings';

  protected formModel: DynamicFormControlModel[] = [
    new DynamicSelectModel({
      id: 'stg_guiprotocol',
      label: 'GUI Protocol',
      options: [
        { label: 'HTTP', value: 'http' },
        { label: 'HTTPS', value: 'https' },
        { label: 'HTTP+HTTPS', value: 'httphttps' },
      ],
    }),
    new DynamicSelectModel({
      id: 'stg_guiaddress',
      label: 'GUI IPv4 Bind Address',
    }),
    new DynamicSelectModel({
      id: 'stg_guiv6address',
      label: 'GUI IPv6 Bind Address',
    }),
    new DynamicInputModel({
      id: 'stg_guiport',
      label: 'GUI HTTP Port',
    }),
    new DynamicInputModel({
      id: 'stg_guihttpsport',
      label: 'GUI HTTPS Port',
    }),
    new DynamicSelectModel({
      id: 'stg_guicertificate',
      label: 'GUI SSL Certificate',
    }),
    new DynamicCheckboxModel({
      id: 'stg_guihttpsredirect',
      label: 'GUI HTTP -> HTTPS Redirect',
    }),
    new DynamicSelectModel({
      id: 'stg_language',
      label: 'GUI Language',
    }),
    new DynamicSelectModel({
      id: 'stg_kbdmap',
      label: 'Console Keyboard map',
    }),
    new DynamicSelectModel({
      id: 'stg_timezone',
      label: 'Timezone',
    }),
    new DynamicSelectModel({
      id: 'stg_sysloglevel',
      label: 'Syslog Level',
    }),
    new DynamicInputModel({
      id: 'stg_syslogserver',
      label: 'Syslog Server',
    }),
  ];

  private stg_guiaddress: DynamicSelectModel<string>;
  private stg_guiv6address: DynamicSelectModel<string>;
  private stg_guicertificate: DynamicSelectModel<string>;
  private stg_language: DynamicSelectModel<string>;
  private stg_kbdmap: DynamicSelectModel<string>;
  private stg_timezone: DynamicSelectModel<string>;
  private stg_sysloglevel: DynamicSelectModel<string>;
  private stg_syslogserver: DynamicSelectModel<string>;

  constructor(protected rest: RestService, protected formService: DynamicFormService) {

  }

  afterInit(entityEdit: any) {
    entityEdit.ws.call('certificate.query', [[['cert_CSR', '=', null]]]).subscribe((res) => {
      this.stg_guicertificate = <DynamicSelectModel<string>>this.formService.findById('stg_guicertificate', this.formModel);
      res.forEach((item) => {
        this.stg_guicertificate.add({ label: item.cert_name, value: item.id });
      });
    });

    entityEdit.ws.call('notifier.choices', ['IPChoices', [true, false]]).subscribe((res) => {
      this.stg_guiaddress = <DynamicSelectModel<string>>this.formService.findById('stg_guiaddress', this.formModel);
      this.stg_guiaddress.add({ label: '0.0.0.0', value: '0.0.0.0' });
      res.forEach((item) => {
        this.stg_guiaddress.add({ label: item[1], value: item[0] });
      });
    });

    entityEdit.ws.call('notifier.choices', ['IPChoices', [false, true]]).subscribe((res) => {
      this.stg_guiv6address = <DynamicSelectModel<string>>this.formService.findById('stg_guiv6address', this.formModel);
      this.stg_guiv6address.add({ label: '::', value: '::' });
      res.forEach((item) => {
        this.stg_guiv6address.add({ label: item[1], value: item[0] });
      });
    });

    entityEdit.ws.call('notifier.gui_languages').subscribe((res) => {
      this.stg_language = <DynamicSelectModel<string>>this.formService.findById('stg_language', this.formModel);
      res.forEach((item) => {
        this.stg_language.add({ label: item[1], value: item[0] });
      });
    });

    entityEdit.ws.call('notifier.choices', ['KBDMAP_CHOICES']).subscribe((res) => {
      this.stg_kbdmap = <DynamicSelectModel<string>>this.formService.findById('stg_kbdmap', this.formModel);
      res.forEach((item) => {
        this.stg_kbdmap.add({ label: item[1], value: item[0] });
      });
    });

    entityEdit.ws.call('notifier.choices', ['TimeZoneChoices']).subscribe((res) => {
      this.stg_timezone = <DynamicSelectModel<string>>this.formService.findById('stg_timezone', this.formModel);
      res.forEach((item) => {
        this.stg_timezone.add({ label: item[1], value: item[0] });
      });
    });

    entityEdit.ws.call('notifier.choices', ['SYS_LOG_LEVEL']).subscribe((res) => {
      this.stg_sysloglevel = <DynamicSelectModel<string>>this.formService.findById('stg_sysloglevel', this.formModel);
      res.forEach((item) => {
        this.stg_sysloglevel.add({ label: item[1], value: item[0] });
      });
    });

  }

}
