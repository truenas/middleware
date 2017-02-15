import { Component } from '@angular/core';
import { Router } from '@angular/router';

import { GlobalState } from '../../../../global.state';
import { RestService } from '../../../../services/rest.service';

@Component({
  selector: 'app-smb-list',
  template: `<entity-list [conf]="this"></entity-list>`
})
export class SMBListComponent {

  protected resource_name: string = 'sharing/cifs/';
  protected route_add: string[] = ['sharing', 'smb', 'add'];
  protected route_edit: string[] = ['sharing', 'smb', 'edit'];
  protected route_delete: string[] = ['sharing', 'smb', 'delete'];

  constructor(_rest: RestService, _router: Router, _state: GlobalState) {

  }

  public columns: any[] = [
    { title: 'Name', name: 'cifs_name' },
    { title: 'Path', name: 'cifs_path' },
  ];
  public config: any = {
    paging: true,
    sorting: { columns: this.columns },
  };

}
