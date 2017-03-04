import { Component } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';


@Component({
  selector: 'app-user-delete',
  template: `<entity-delete [conf]="this"></entity-delete>`
})
export class UserDeleteComponent {

  protected resource_name: string = 'account/users';
  protected route_success: string[] = ['users'];

}
