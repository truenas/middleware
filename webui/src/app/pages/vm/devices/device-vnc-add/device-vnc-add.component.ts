import { ApplicationRef, Component, Injector, OnInit, ViewContainerRef } from '@angular/core';
import { FormGroup } from '@angular/forms';
import { Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { GlobalState } from '../../../../global.state';
import { RestService, WebSocketService } from '../../../../services/';

@Component({
  selector: 'app-device-add',
  template: `<entity-add [conf]="this"></entity-add>`
})
export class DeviceVncAddComponent {

  protected resource_name: string = 'vm/device';
  protected route_success: string[] = ['vm', 'devices'];
  protected formModel: DynamicFormControlModel[] = [
    new DynamicInputModel({
        id: 'foo',
        label: 'foo',
    }),
  ];

  constructor(protected router: Router, protected rest: RestService, protected ws: WebSocketService, protected formService: DynamicFormService, protected _injector: Injector, protected _appRef: ApplicationRef, protected _state: GlobalState) {

  }

}
