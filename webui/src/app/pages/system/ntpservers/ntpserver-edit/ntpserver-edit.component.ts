import { Component } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { RestService } from '../../../../services/rest.service';

@Component({
  selector: 'app-ntpserver-edit',
  template: `<entity-edit [conf]="this"></entity-edit>`
})
export class NTPServerEditComponent {

  protected resource_name: string = 'system/ntpserver';
  protected route_delete: string[] = ['system', 'ntpservers', 'delete'];
  protected route_success: string[] = ['system', 'ntpservers'];

  protected formModel: DynamicFormControlModel[] = [
    new DynamicInputModel({
      id: 'ntp_address',
      label: 'Address',
    }),
    new DynamicCheckboxModel({
      id: 'ntp_burst',
      label: 'Burst',
    }),
    new DynamicCheckboxModel({
      id: 'ntp_iburst',
      label: 'IBurst',
      value: true,
    }),
    new DynamicCheckboxModel({
      id: 'ntp_prefer',
      label: 'Prefer',
    }),
    new DynamicInputModel({
      id: 'ntp_minpoll',
      label: 'Min. Poll',
      value: 6,
    }),
    new DynamicInputModel({
      id: 'ntp_maxpoll',
      label: 'Max. Poll',
      value: 10,
    }),
    new DynamicCheckboxModel({
      id: 'force',
      label: 'Force',
    }),
  ];

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected formService: DynamicFormService) {

  }

  afterInit(entityEdit) {
  }

}
