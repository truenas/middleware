import { Component, ElementRef } from '@angular/core';
import { Router } from '@angular/router';

import { GlobalState } from '../../../../global.state';
import { RestService } from '../../../../services/rest.service';

@Component({
  selector: 'app-snapshot-list',
  template: `<entity-list [conf]="this"></entity-list>`
})
export class SnapshotListComponent {

  protected resource_name: string = 'storage/snapshot';
  protected route_delete: string[] = ['storage', 'snapshots', 'delete'];
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

  constructor(_rest: RestService, private _router: Router, _state: GlobalState, _eRef: ElementRef) {
  }

  isActionVisible(actionId: string, row: any) {
    if(actionId == 'edit' || actionId == 'add') {
      return false;
    }
    return true;
  }

  getActions(row) {
    let actions = [];
    actions.push({
      label: "Delete",
      onClick: (row) => {
        this._router.navigate(new Array('/pages').concat(["storage", "snapshots", "delete", row.id]));
      }
    });
    actions.push({
      label: "Clone",
      onClick: (row) => {
        this._router.navigate(new Array('/pages').concat(["storage", "snapshots", "clone", row.id]));
      }
    });
    if(row.mostrecent) {
      actions.push({
        label: "Rollback",
        onClick: (row) => {
          this._router.navigate(new Array('/pages').concat(["storage", "snapshots", "rollback", row.id]));
        }
      });
    }
    return actions;
  }

}
