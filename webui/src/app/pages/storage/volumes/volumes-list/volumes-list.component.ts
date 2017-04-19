import { Component, ElementRef, OnInit } from '@angular/core';
import { Router } from '@angular/router';

import { GlobalState } from '../../../../global.state';
import { RestService } from '../../../../services/rest.service';

import filesize from 'filesize.js';

@Component({
  selector: 'app-volumes-list',
  template: `<entity-list [conf]="this"></entity-list>`
})
export class VolumesListComponent {

  protected resource_name: string = 'storage/volume/';
  protected route_add: string[] = ['storage', 'volumes', 'manager'];

  constructor(_rest: RestService, private _router: Router, _state: GlobalState, _eRef: ElementRef) {

  }

  public columns:Array<any> = [
    {title: 'Name', name: 'name'},
    {title: 'Status', name: 'status'},
    {title: 'Available', name: 'avail'},
    {title: 'Used', name: 'used'},
  ];
  public config:any = {
    paging: true,
    sorting: {columns: this.columns},
  };

  rowValue(row, attr) {
    switch(attr) {
      case 'avail':
        return filesize(row[attr]);
      case 'used':
        return filesize(row[attr]) + " (" + row['used_pct'] + ")";
      default:
        return row[attr];
    }
  }

  getActions(row) {
    let actions = [];
    if(row.vol_fstype == "ZFS") {
      actions.push({
        label: "Delete",
        onClick: (row) => {
          this._router.navigate(new Array('/pages').concat(["storage", "volumes", "delete", row.id]));
        }
      });
    }
    if(row.type == "dataset") {
      actions.push({
        label: "Add Dataset",
        onClick: (row) => {
          this._router.navigate(new Array('/pages').concat(["storage", "volumes", "id", row.path.split('/')[0], "dataset", "add", row.path]));
        }
      });
      actions.push({
        label: "Create Snapshot",
        onClick: (row) => {
          this._router.navigate(new Array('/pages').concat(["storage", "snapshots", "id", row.path.split('/')[0], "add"]));
        }
      });

      if(row.path.indexOf('/') != -1) {
        actions.push({
          label: "Delete Dataset",
          onClick: (row) => {
            this._router.navigate(new Array('/pages').concat(["storage", "volumes", "id", row.path.split('/')[0], "dataset", "delete", row.path]));
          }
        });
      }
    }
    return actions;
  }

}
