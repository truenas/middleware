import { Component, Input, OnInit } from '@angular/core';
import { Router } from '@angular/router';

import { EntityListComponent } from './entity-list.component';
import { GlobalState } from '../../../../global.state';
import { RestService } from '../../../../services/rest.service';

import { Subscription } from 'rxjs';

@Component({
  selector: 'app-entity-list-add-actions',
  template: `
    <span *ngFor="let action of actions">
      <button class="btn btn-primary btn-add" (click)="action.onClick()">{{ action?.label }}</button>
    </span>
  `
})
export class EntityListAddActionsComponent implements OnInit {

  @Input('entity') entity: EntityListComponent;

  private actions: any[];

  ngOnInit() {
    this.actions = this.entity.getAddActions();
  }

}
