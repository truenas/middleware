import { ApplicationRef, Component, Injector, OnInit, ViewContainerRef } from '@angular/core';
import { FormGroup } from '@angular/forms';
import { Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { GlobalState } from '../../../global.state';
import { RestService, WebSocketService } from '../../../services/';

@Component({
  selector: 'app-vm-add',
  template: `<entity-add [conf]="this"></entity-add>`
})
export class VmAddComponent {

  protected resource_name: string = 'vm/vm/';
  protected route_success: string[] = ['vm'];
  protected formModel: DynamicFormControlModel[] = [
    new DynamicInputModel({
      id: 'name',
      label: 'Name',
    }),
    new DynamicInputModel({
        id: 'description',
        label: 'Description',
    }),
    new DynamicInputModel({
        id: 'vcpus',
        label: 'Virtual CPUs',
    }),
    new DynamicInputModel({
      id: 'memory',
      label: 'Memory Size (MiB)',
    }),
    new DynamicSelectModel({
        id: 'bootloader',
        label: 'Boot Loader Type',
    }),
  ];
  private bootloader: DynamicSelectModel<string>;
  public bootloader_type: any[];

  constructor(protected router: Router, protected rest: RestService, protected ws: WebSocketService, protected formService: DynamicFormService, protected _injector: Injector, protected _appRef: ApplicationRef, protected _state: GlobalState) {

  }

  afterInit(entityAdd: any) {
    entityAdd.ws.call('notifier.choices', ['VM_BOOTLOADER']).subscribe((res) => { 
      this.bootloader = <DynamicSelectModel<string>> this.formService.findById("bootloader", this.formModel);
      this.bootloader_type = res;
      res.forEach((item) => {
        this.bootloader.add({label: item[1], value: item[0]});
      });
      entityAdd.formGroup.controls['bootloader'].setValue(this.bootloader_type[1][0]);
    });
  }

}
