import { Component } from '@angular/core';

@Component({
  selector: 'app-user-list',
  template: `<entity-list [conf]="this"></entity-list>`
})
export class UserListComponent {

  protected resource_name: string = 'account/users';
  protected route_add: string[] = ['users', 'add'];
  protected route_edit: string[] = ['users', 'edit'];
  protected route_delete: string[] = ['users', 'delete'];

  public columns:Array<any> = [
    {title: 'Username', name: 'bsdusr_username'},
    {title: 'UID', name: 'bsdusr_uid'},
    {title: 'GID', name: 'bsdusr_group'},
    {title: 'Home directory', name: 'bsdusr_home'},
    {title: 'Shell', name: 'bsdusr_shell'},
    {title: 'Builtin', name: 'bsdusr_builtin'},
  ];
  public config:any = {
    paging: true,
    sorting: {columns: this.columns},
  };

  isActionVisible(actionId: string, row: any) {
    if(actionId == 'delete' && row.bsdusr_builtin === true) {
      return false;
    }
    return true;
  }

}
