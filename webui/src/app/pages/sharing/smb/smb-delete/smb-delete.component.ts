import { Component } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { RestService } from '../../../../services/';

@Component({
  selector: 'app-group-delete',
  template: `<entity-delete [conf]="this"></entity-delete>`
})
export class SMBDeleteComponent {

  protected resource_name: string = 'sharing/cifs/';
  protected route_success: string[] = ['sharing', 'smb'];

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService) {

  }

}
