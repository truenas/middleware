import { Component } from '@angular/core';

@Component({
  selector: 'app-user-list',
  template: `<entity-list [conf]="this"></entity-list>`
})
export class VmListComponent {

  protected resource_name: string = 'vm/vm';
  protected route_add: string[] = ['vm', 'add'];
  protected route_edit: string[] = ['vm', 'edit'];
  protected route_delete: string[] = ['vm', 'delete'];

  public columns:Array<any> = [
    {title: 'Name', name: 'name'},
    {title: 'Description', name: 'description'},
    {title: 'Info', name: ''},
    {title: 'Virtual CPUs', name: 'vcpus'},
    {title: 'Memory Size (MiB)', name: 'memory'},
    {title: 'Boot Loader Type', name: 'bootloader'},
  ];
  public config:any = {
    paging: true,
    sorting: {columns: this.columns},
  };

  isActionVisible(actionId: string, row: any) {
    if(actionId == 'delete' && row.id === true) {
      return false;
    }
    return true;
  }

}
