import { Component } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { RestService } from '../../../../services/';

@Component({
  selector: 'app-smb-edit',
  template: `<entity-edit [conf]="this"></entity-edit>`
})
export class SMBEditComponent {

  protected resource_name: string = 'sharing/cifs/';
  protected route_delete: string[] = ['sharing', 'smb', 'delete'];
  protected route_success: string[] = ['sharing', 'smb'];

  protected formModel: DynamicFormControlModel[] = [
    new DynamicInputModel({
      id: 'cifs_name',
      label: 'Name',
    }),
    new DynamicInputModel({
      id: 'cifs_path',
      label: 'Path',
    }),
    new DynamicSelectModel({
      id: 'cifs_vfsobjects',
      label: 'VFS Objects',
      multiple: true,
    }),
  ];

  private cifs_vfsobjects: DynamicSelectModel<string>;

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected formService: DynamicFormService) {

  }

  afterInit(entityEdit: any) {
    entityEdit.ws.call('notifier.choices', ['CIFS_VFS_OBJECTS']).subscribe((res) => {
      this.cifs_vfsobjects = <DynamicSelectModel<string>>this.formService.findById("cifs_vfsobjects", this.formModel);
      res.forEach((item) => {
        this.cifs_vfsobjects.add({ label: item[1], value: item[0] });
      });
    });
  }

}
