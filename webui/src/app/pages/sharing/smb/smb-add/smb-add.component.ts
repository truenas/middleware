import { Component, ViewContainerRef } from '@angular/core';
import { Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { GlobalState } from '../../../../global.state';
import { RestService, WebSocketService } from '../../../../services/';

@Component({
  selector: 'app-smb-add',
  template: `<entity-add [conf]="this"></entity-add>`
})
export class SMBAddComponent {

  protected resource_name: string = 'sharing/cifs/';
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

  constructor(protected router: Router, protected rest: RestService, protected ws: WebSocketService, protected formService: DynamicFormService, protected _state: GlobalState) {

  }

  afterInit(entityAdd: any) {
    entityAdd.ws.call('notifier.choices', ['CIFS_VFS_OBJECTS']).subscribe((res) => {
      this.cifs_vfsobjects = <DynamicSelectModel<string>>this.formService.findById("cifs_vfsobjects", this.formModel);
      res.forEach((item) => {
        this.cifs_vfsobjects.add({ label: item[1], value: item[0] });
      });
    });
  }

}
