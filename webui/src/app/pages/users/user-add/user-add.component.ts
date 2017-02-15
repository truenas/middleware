import { ApplicationRef, Component, Injector, OnInit, ViewContainerRef } from '@angular/core';
import { FormGroup } from '@angular/forms';
import { Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { GlobalState } from '../../../global.state';
import { RestService, WebSocketService } from '../../../services/';

@Component({
  selector: 'app-user-add',
  template: `<entity-add [conf]="this"></entity-add>`
})
export class UserAddComponent {

  protected route_success: string[] = ['users'];
  protected resource_name: string = 'account/users/';
  protected formModel: DynamicFormControlModel[] = [
    new DynamicInputModel({
      id: 'bsdusr_uid',
      label: 'UID',
      validators: {required: null},
    }),
    new DynamicInputModel({
        id: 'bsdusr_username',
        label: 'Username',
    }),
    new DynamicInputModel({
        id: 'bsdusr_full_name',
        label: 'Full Name',
    }),
    new DynamicInputModel({
      id: 'bsdusr_home',
      label: 'Home Directory',
    }),
    new DynamicInputModel({
        id: 'bsdusr_email',
        label: 'Email',
    }),
    new DynamicInputModel({
        id: 'bsdusr_password',
        label: 'Password',
        inputType: 'password',
    }),
    new DynamicSelectModel({
      id: 'bsdusr_group',
      label: 'Primary Group',
      options: [],
      relation: [
        {
          action: 'DISABLE',
          when: [
            {
              id: 'bsdusr_creategroup',
              value: true,
            }
          ]
        },
      ],
    }),
    new DynamicCheckboxModel({
        id: 'bsdusr_creategroup',
        label: 'Create Primary Group',
    }),
    new DynamicSelectModel({
        id: 'bsdusr_shell',
        label: 'Shell',
    }),
  ];
  public shells: any[];
  private bsdusr_shell: DynamicSelectModel<string>;
  private bsdusr_group: DynamicSelectModel<string>;

  constructor(protected router: Router, protected rest: RestService, protected ws: WebSocketService, protected formService: DynamicFormService, protected _injector: Injector, protected _appRef: ApplicationRef, protected _state: GlobalState) {

  }

  afterInit(entityAdd: any) {
    this.rest.get('account/groups/', {}).subscribe((res) => {
      this.bsdusr_group = <DynamicSelectModel<string>> this.formService.findById("bsdusr_group", this.formModel);
      res.data.forEach((item) => {
        this.bsdusr_group.add({label: item.bsdgrp_group, value: item.id});
      });
      this.bsdusr_group.valueUpdates.next();
    });
    this.rest.get(this.resource_name, {}).subscribe((res) => {
      let uid = 999;
      res.data.forEach((item, i) => {
        if(item.bsdusr_uid > uid) uid = item.bsdusr_uid;
      });
      uid += 1;
      entityAdd.formGroup.controls['bsdusr_uid'].setValue(uid);
    });
    entityAdd.ws.call('notifier.choices', ['SHELL_CHOICES']).subscribe((res) => {
      this.bsdusr_shell = <DynamicSelectModel<string>> this.formService.findById("bsdusr_shell", this.formModel);
      this.shells = res;
      res.forEach((item) => {
        this.bsdusr_shell.add({ label: item[1], value: item[0] });
      });
      entityAdd.formGroup.controls['bsdusr_shell'].setValue(this.shells[1][0]);
    });
  }

  clean_uid(value) {
    if(value['uid'] == null) {
      delete value['uid'];
    }
    return value;
  }

}
