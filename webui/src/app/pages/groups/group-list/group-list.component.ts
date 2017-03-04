import { Component, ElementRef, OnInit } from '@angular/core';
import { Router } from '@angular/router';

import { GlobalState } from '../../../global.state';
import { RestService } from '../../../services/rest.service';

import { EntityListComponent } from '../../common/entity/entity-list/index';

@Component({
  selector: 'app-group-list',
  template: `
    <entity-list [conf]="this"></entity-list>
  `,
})
export class GroupListComponent {

  protected resource_name: string = 'account/groups/';
  protected route_add: string[] = ['groups', 'add'];
  protected route_edit: string[] = ['groups', 'edit'];
  protected route_delete: string[] = ['groups', 'delete'];

  public columns:Array<any> = [
    {title: 'Group', name: 'bsdgrp_group'},
    {title: 'GID', name: 'bsdgrp_gid'},
    {title: 'Builtin', name: 'bsdgrp_builtin'},
  ];
  public config:any = {
    paging: true,
    sorting: {columns: this.columns},
  };

  isActionVisible(actionId: string, row: any) {
    if(actionId == 'delete' && row.bsdgrp_builtin === true) {
      return false;
    }
    return true;
  }

}
