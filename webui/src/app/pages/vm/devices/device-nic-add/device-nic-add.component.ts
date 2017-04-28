import { ApplicationRef, Component, Injector, OnInit, ViewContainerRef } from '@angular/core';
import { FormGroup } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { GlobalState } from '../../../../global.state';
import { RestService, WebSocketService } from '../../../../services/';

@Component({
  selector: 'app-device-nic-add',
  template: `<device-add [conf]="this"></device-add>`
})
export class DeviceNicAddComponent {

  protected resource_name: string = 'vm/device';
  protected pk: any;
  protected route_success: string[];
  protected vm: string;
  private nicType: DynamicSelectModel<string>;

  protected dtype: string = 'NIC';

  protected formModel: DynamicFormControlModel[] = [
    new DynamicSelectModel({
        id: 'type',
        label: 'Network Interface',
    }),
  ];


  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected ws: WebSocketService, protected formService: DynamicFormService, protected _injector: Injector, protected _appRef: ApplicationRef, protected _state: GlobalState) {

  }

  afterInit(entityAdd: any) {
    this.route.params.subscribe(params => {
        this.pk = params['pk'];
        this.vm = params['name'];
        this.route_success = ['vm', this.pk, 'devices', this.vm];
    });
    entityAdd.ws.call('notifier.choices', ['VM_NICTYPES']).subscribe((res) => {
      this.nicType = <DynamicSelectModel<string>>this.formService.findById("type", this.formModel);
      res.forEach((item) => {
        this.nicType.add({ label: item[1], value: item[0] });
      });
    });
  }


}
