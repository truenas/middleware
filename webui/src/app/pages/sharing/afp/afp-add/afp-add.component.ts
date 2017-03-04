import { Component, ViewContainerRef } from '@angular/core';
import { Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { GlobalState } from '../../../../global.state';
import { RestService, WebSocketService } from '../../../../services/';

@Component({
  selector: 'app-afp-add',
  template: `<entity-add [conf]="this"></entity-add>`
})
export class AFPAddComponent {

  protected route_success: string[] = ['sharing', 'afp'];
  protected resource_name: string = 'sharing/afp/';

  protected formModel: DynamicFormControlModel[] = [
    new DynamicInputModel({
      id: 'afp_name',
      label: 'Name',
    }),
    new DynamicInputModel({
      id: 'afp_path',
      label: 'Path',
    }),
  ];

  constructor(protected router: Router, protected rest: RestService, protected ws: WebSocketService, protected formService: DynamicFormService, protected _state: GlobalState) {

  }

  afterInit(entityAdd: any) {
  }

}
