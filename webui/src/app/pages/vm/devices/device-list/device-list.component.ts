import { Component, ElementRef, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { GlobalState } from '../../../../global.state';
import { RestService, WebSocketService } from '../../../../services/';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-device-list',
  template: `
  <h1> VM: {{ this.vm }} Devices </h1>
  <entity-list [conf]="this"></entity-list>
  `
})
export class DeviceListComponent {

  protected resource_name: string;
  protected route_edit: string[] = ['vm', 'devices', 'edit'];
  protected route_delete: string[] = ['vm', 'devices', 'delete'];
  protected pk: any;
  protected vm: string;
  private sub: Subscription;

  constructor(protected router: Router, protected aroute: ActivatedRoute, protected rest: RestService, protected ws: WebSocketService) {}

  public columns:Array<any> = [
    {title: 'Type', name: 'dtype'},
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

  getAddActions() {
    let actions = [];
    actions.push({
        label: "Add CDROM",
        onClick: () => {
            this.router.navigate(new Array('/pages').concat(["vm", this.pk, "devices", this.vm , "cdrom", "add" ]));
        }
    });
    actions.push({
        label: "Add NIC",
        onClick: () => {
            this.router.navigate(new Array('/pages').concat(["vm", this.pk, "devices", this.vm , "nic", "add" ]));
        }
    });
    actions.push({
        label: "Add Disk",
        onClick: () => {
            this.router.navigate(new Array('/pages').concat(["vm", this.pk, "devices", this.vm ,"disk", "add" ]));
        }
    });
    actions.push({
        label: "Add VNC",
        onClick: () => {
            this.router.navigate(new Array('/pages').concat(["vm", this.pk, "devices", this.vm , "vnc", "add" ]));
        }
    });
    return actions;
  }

  preInit(entityList: any) {
    this.sub = this.aroute.params.subscribe(params => {
      this.pk = params['pk'];
      this.vm = params['name'];
      // this is filter by vm's id to show devices belonging to that VM.
      this.resource_name = 'vm/device/?vm__id=' + this.pk;
    });
  }
}
