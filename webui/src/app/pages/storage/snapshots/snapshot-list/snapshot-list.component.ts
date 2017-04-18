import { Component } from '@angular/core';

@Component({
  selector: 'app-snapshot-list',
  template: `<entity-list [conf]="this"></entity-list>`
})
export class SnapshotListComponent {

  protected resource_name: string = 'storage/snapshot';
  protected route_add: string[] = ['storage', 'snapshot', 'add'];
  protected route_delete: string[] = ['storage', 'snapshot', 'delete'];
//  protected route_clone: string[] = ['snapshot', 'clone'];

  public columns:Array<any> = [
    {title: 'Filesystem', name: 'filesystem'},
    {title: 'Fullname', name: 'fullname'},
    {title: 'Id', name: 'id'},
    {title: 'Most Recent', name: 'mostrecent'},
    {title: 'Name', name: 'name'},
    {title: 'Parent Type', name: 'parent_type'},
    {title: 'Used', name: 'used'},
    {title: 'Refer', name: 'refer'}
  ];
  public config:any = {
    paging: true,
    sorting: {columns: this.columns},
  };

}
