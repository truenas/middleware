import { Component } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { RestService } from '../../../../services/';

@Component({
  selector: 'app-group-delete',
  template: `<entity-delete [conf]="this"></entity-delete>`
})
export class AFPDeleteComponent {

  protected resource_name: string = 'sharing/afp/';
  protected route_success: string[] = ['sharing', 'afp'];

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService) {

  }

}
