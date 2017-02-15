import { Component } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { RestService } from '../../../../services/';

@Component({
  selector: 'app-afp-edit',
  template: `<entity-edit [conf]="this"></entity-edit>`
})
export class AFPEditComponent {

  protected resource_name: string = 'sharing/afp/';
  protected route_delete: string[] = ['sharing', 'afp', 'delete'];
  protected route_success: string[] = ['sharing', 'afp'];

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

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected formService: DynamicFormService) {

  }

  afterInit(entityEdit: any) {
  }

}
