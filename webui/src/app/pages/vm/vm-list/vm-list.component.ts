import { Component, ElementRef, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { GlobalState } from '../../../global.state';
import { RestService, WebSocketService } from '../../../services/';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-vm-list',
  template: `
  <entity-list [conf]="this"></entity-list>
  `
})
export class VmListComponent {

  protected resource_name: string = 'vm/vm';
  protected route_add: string[] = ['vm', 'add'];
  protected route_edit: string[] = ['vm', 'edit'];
  protected route_delete: string[] = ['vm', 'delete'];

  constructor(protected router: Router, protected rest: RestService, protected ws: WebSocketService) {}

  public columns:Array<any> = [
    {title: 'Name', name: 'name'},
    {title: 'Description', name: 'description'},
    {title: 'Info', name: 'info'},
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

  getActions(row) {
    let actions = [];
    actions.push({
        label: "Start",
    });
    actions.push({
        label: "Edit",
        onClick: (row) => {
            this.router.navigate(new Array('/pages').concat(["vm", "edit", row.id]));
        }
    });
    actions.push({
        label: "Delete",
        onClick: (row) => {
            this.router.navigate(new Array('/pages').concat(["vm", "delete", row.id]));
        },
    });
    actions.push({
        label: "Devices",
        onClick: (row) => {
            this.router.navigate(new Array('/pages').concat(["vm", row.id, "devices", row.name]));
        }
    });
    return actions;
  }

}
