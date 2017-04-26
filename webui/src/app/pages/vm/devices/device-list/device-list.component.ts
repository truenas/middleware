import { Component, ElementRef, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { GlobalState } from '../../../../global.state';
import { RestService, WebSocketService } from '../../../../services/';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-device-list',
  template: `
  <entity-list [conf]="this"></entity-list>
  `
})
export class DeviceListComponent {

  protected resource_name: string = 'vm/device';
  protected route_edit: string[] = ['vm', 'devices', 'edit'];
  protected route_delete: string[] = ['vm', 'devices', 'delete'];
  protected pk: any;
  private sub: Subscription;

  constructor(protected router: Router, protected aroute: ActivatedRoute, protected rest: RestService, protected ws: WebSocketService) {}

  public columns:Array<any> = [
    {title: 'VM Id', name: 'id'},
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
            this.router.navigate(new Array('/pages').concat(["vm", this.pk, "devices", "cdrom", "add" ]));
        }
    });
    return actions;
  }

  afterInit(entityAdd: any) {
    this.sub = this.aroute.params.subscribe(params => {
      this.pk = params['pk'];
    });
  }
}
