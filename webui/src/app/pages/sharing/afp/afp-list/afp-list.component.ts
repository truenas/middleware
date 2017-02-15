import { Component } from '@angular/core';
import { Router } from '@angular/router';

import { GlobalState } from '../../../../global.state';
import { RestService } from '../../../../services/rest.service';

@Component({
  selector: 'app-afp-list',
  template: `<entity-list [conf]="this"></entity-list>`
})
export class AFPListComponent {

  protected resource_name: string = 'sharing/afp/';
  protected route_add: string[] = ['sharing', 'afp', 'add'];
  protected route_edit: string[] = ['sharing', 'afp', 'edit'];
  protected route_delete: string[] = ['sharing', 'afp', 'delete'];

  constructor(_rest: RestService, _router: Router, _state: GlobalState) {

  }

  public columns: any[] = [
    { title: 'Name', name: 'afp_name' },
    { title: 'Path', name: 'afp_path' },
  ];
  public config: any = {
    paging: true,
    sorting: { columns: this.columns },
  };

}
