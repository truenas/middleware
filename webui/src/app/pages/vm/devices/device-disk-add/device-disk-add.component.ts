import { ApplicationRef, Component, Injector, OnInit, ViewContainerRef } from '@angular/core';
import { FormGroup } from '@angular/forms';
import { Router, ActivatedRoute} from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { GlobalState } from '../../../../global.state';
import { RestService, WebSocketService } from '../../../../services/';

@Component({
  selector: 'app-device-disk-add',
  template: `<device-add [conf]="this"></device-add>`
})
export class DeviceDiskAddComponent {

  protected resource_name: string = 'vm/device';
  protected pk: any;
  protected route_success: string[];
  protected formModel: DynamicFormControlModel[] = [
    new DynamicInputModel({
      id: 'zvol',
      label: 'ZVol',
    }),
    new DynamicSelectModel({
      id: 'mode',
      label: 'Mode',
      options: [
        { label: 'AHCI', value: "AHCI" },
        { label: 'VirtIO', value: "VirtIO" },
      ],
    }),
  ];

  afterInit() {
    this.route.params.subscribe(params => {
        this.pk = params['pk'];
        this.route_success = ['vm', this.pk, 'devices'];
    });
  }

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected ws: WebSocketService, protected formService: DynamicFormService, protected _injector: Injector, protected _appRef: ApplicationRef, protected _state: GlobalState) {

  }

}
