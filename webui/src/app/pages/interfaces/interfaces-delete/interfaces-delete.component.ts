import { ApplicationRef, Component, Injector, OnInit, ViewContainerRef } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { RestService } from '../../../services/rest.service';

@Component({
  selector: 'app-group-delete',
  template: `<entity-delete [conf]="this"></entity-delete>`
})
export class InterfacesDeleteComponent {

  protected resource_name: string = 'network/interface/';
  protected route_success: string[] = ['network', 'interfaces'];

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected _injector: Injector, protected _appRef: ApplicationRef) {

  }

}
