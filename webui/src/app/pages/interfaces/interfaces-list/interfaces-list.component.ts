import { Component } from '@angular/core';
import { Router } from '@angular/router';

import { GlobalState } from '../../../global.state';
import { RestService } from '../../../services/rest.service';

@Component({
  selector: 'app-interfaces-list',
  template: `<entity-list [conf]="this"></entity-list>`
})
export class InterfacesListComponent {

  protected resource_name: string = 'network/interface/';
  protected route_add: string[] = ['interfaces', 'add'];
  protected route_edit: string[] = ['interfaces', 'edit'];
  protected route_delete: string[] = ['interfaces', 'delete'];

  constructor(_rest: RestService, _router: Router, _state: GlobalState) {

  }

  public columns:Array<any> = [
    {title: 'Interface', name: 'int_interface'},
    {title: 'Name', name: 'int_name'},
    {title: 'Media Status', name: 'int_media_status'},
    {title: 'DHCP', name: 'int_dhcp'},
    {title: 'IPv4 Addresses', name: 'ipv4_addresses'},
    {title: 'IPv6 Addresses', name: 'ipv6_addresses'},
  ];
  public config:any = {
    paging: true,
    sorting: {columns: this.columns},
  };

  rowValue(row, attr) {
    if(attr == 'ipv4_addresses' || attr == 'ipv6_addresses') {
      return row[attr].join(', ');
    }
    return row[attr];
  }

}
