import { Component } from '@angular/core';
import { FormGroup } from '@angular/forms';
import { Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { GlobalState } from '../../../../global.state';
import { RestService, WebSocketService } from '../../../../services/';

@Component({
  selector: 'app-ntpserver-add',
  template: `<entity-add [conf]="this"></entity-add>`
})
export class NTPServerAddComponent {

  protected route_success: string[] = ['system', 'ntpservers'];
  protected resource_name: string = 'system/ntpserver';
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

  constructor(protected router: Router, protected rest: RestService, protected ws: WebSocketService, protected formService: DynamicFormService, protected _state: GlobalState) {
  }

  afterInit(entityAdd: any) {
  }

}
