import { Component } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { RestService } from '../../../../services/rest.service';

@Component({
  selector: 'app-vm-device-delete',
  template: `<entity-delete [conf]="this"></entity-delete>`
})
export class DeviceDeleteComponent {

  protected resource_name: string = 'vm/device/';
  protected route_success: string[] = ['vm', 'devices'];

}
