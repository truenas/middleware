import { ApplicationRef, Component, Injector, OnInit, ViewContainerRef } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { RestService } from '../../../services/rest.service';

@Component({
  selector: 'app-vm-edit',
  template: `<entity-edit [conf]="this"></entity-edit>`
})
export class VmEditComponent {

  protected resource_name: string = 'vm/vm';
  protected route_delete: string[] = ['vm', 'delete'];
  protected route_success: string[] = ['vm'];

  protected formModel: DynamicFormControlModel[] = [
    new DynamicInputModel({
      id: 'name',
      label: 'name',
      validators: { required: null },
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
  public bootloader_type: any[]

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected formService: DynamicFormService, protected _injector: Injector, protected _appRef: ApplicationRef) {

  }

  afterInit(entityEdit) {
    entityEdit.ws.call('notifier.choices', ['VM_BOOTLOADER']).subscribe((res) => {
      this.bootloader = <DynamicSelectModel<string>>this.formService.findById("bootloader", this.formModel);
      this.bootloader_type = res
      res.forEach((item) => {
        this.bootloader.add({ label: item[1], value: item[0]});
      });
      entityEdit.formGroup.controls['bootloader'].setValue(this.bootloader_type[1][0]);
    });
  }

}
