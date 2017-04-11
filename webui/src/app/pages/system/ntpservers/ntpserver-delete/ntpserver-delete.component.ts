import { Component } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';


@Component({
  selector: 'app-ntpserver-delete',
  template: `<entity-delete [conf]="this"></entity-delete>`
})
export class NTPServerDeleteComponent {

  protected resource_name: string = 'system/ntpserver';
  protected route_success: string[] = ['system', 'ntpservers'];

}
