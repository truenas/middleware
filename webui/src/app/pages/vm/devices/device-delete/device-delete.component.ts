import { Component } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { RestService } from '../../../../services/rest.service';

@Component({
  selector: 'app-vm-device-delete',
  template: `<entity-delete [conf]="this"></entity-delete>`
})
export class DeviceDeleteComponent {

  protected resource_name: string = 'vm/device';
  protected route_success: string[];
  protected vmid: any;
  protected vm: string;
  protected skipGet: boolean = true;

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService ) {
  }

  afterInit(deviceAdd: any) {
    this.route.params.subscribe(params => {
      this.vmid = params['vmid'];
      this.vm = params['name'];
      this.route_success = ['vm', this.vmid, 'devices', this.vm];
    });
  }
}
