import { ApplicationRef, Component, Injector, OnInit, ViewContainerRef } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { RestService } from '../../../../services/rest.service';

@Component({
  selector: 'app-volume-delete',
  template: `<entity-delete [conf]="this"></entity-delete>`
})
export class VolumeDeleteComponent {

  protected resource_name: string = 'storage/volume/';
  protected route_success: string[] = ['volumes'];

}
