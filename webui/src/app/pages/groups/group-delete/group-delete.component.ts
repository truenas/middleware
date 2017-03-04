import { ApplicationRef, Component, Injector, OnInit, ViewContainerRef } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { RestService } from '../../../services/rest.service';

@Component({
  selector: 'app-group-delete',
  template: `<entity-delete [conf]="this"></entity-delete>`
})
export class GroupDeleteComponent {

  protected resource_name: string = 'account/groups/';
  protected route_success: string[] = ['groups'];

}
