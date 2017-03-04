import { Component } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicTextAreaModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { RestService } from '../../../../services/';

@Component({
  selector: 'app-nfs-edit',
  template: `<entity-edit [conf]="this"></entity-edit>`
})
export class NFSEditComponent {

  protected resource_name: string = 'sharing/nfs/';
  protected route_delete: string[] = ['sharing', 'nfs', 'delete'];
  protected route_success: string[] = ['sharing', 'nfs'];

  protected formModel: DynamicFormControlModel[] = [
    new DynamicInputModel({
      id: 'nfs_comment',
      label: 'Comment',
    }),
    new DynamicInputModel({
      id: 'path',
      label: 'Path',
    }),
    new DynamicTextAreaModel({
      id: 'nfs_network',
      label: 'Network',
    }),
    new DynamicTextAreaModel({
      id: 'nfs_hosts',
      label: 'Hosts',
    }),
    new DynamicCheckboxModel({
      id: 'nfs_alldirs',
      label: 'All dirs',
    }),
  ];

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected formService: DynamicFormService) {

  }

  afterInit(entityEdit: any) {
  }

  initial(entityEdit) {
    entityEdit.formGroup.controls.path.setValue(entityEdit.data.nfs_paths.join(' '));
  }

  clean(data) {
    data.nfs_paths = data.path.split(' ');
    delete data.path;
    return data;
  }

}
