import { Component } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { RestService } from '../../../services/rest.service';

@Component({
  selector: 'app-vm-delete',
  template: `<entity-delete [conf]="this"></entity-delete>`
})
export class VmDeleteComponent {

  protected resource_name: string = 'vm/vm/';
  protected route_success: string[] = ['vm'];

}
