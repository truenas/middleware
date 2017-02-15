import { Component } from '@angular/core';
import { Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { GlobalState } from '../../../global.state';
import { RestService, WebSocketService } from '../../../services/';

@Component({
  selector: 'app-group-add',
  template: `<entity-add [conf]="this"></entity-add>`
})
export class GroupAddComponent {

  protected route_success: string[] = ['groups'];
  protected resource_name: string = 'account/groups/';

  protected formModel: DynamicFormControlModel[] = [
    new DynamicInputModel({
        id: 'bsdgrp_gid',
        label: 'GID',
    }),
    new DynamicInputModel({
        id: 'bsdgrp_group',
        label: 'Name',
    }),
  ];
  public users: any[];

  constructor(protected router: Router, protected rest: RestService, protected ws: WebSocketService, protected formService: DynamicFormService) {

  }

  afterInit(entityAdd: any) {
    this.rest.get('account/users/', {limit: 0}).subscribe((res) => {
      this.users = res.data;
    });

    this.rest.get(this.resource_name, {limit: 0, bsdgrp_builtin: false}).subscribe((res) => {
      let gid = 999;
      res.data.forEach((item, i) => {
        if(item.bsdgrp_gid > gid) gid = item.bsdgrp_gid;
      });
      gid += 1;
      entityAdd.formGroup.controls['bsdgrp_gid'].setValue(gid);
    });

  }

}
