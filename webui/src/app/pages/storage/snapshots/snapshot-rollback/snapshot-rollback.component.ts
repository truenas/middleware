import { ApplicationRef, Component, Input, Injector, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { RestService, WebSocketService } from '../../../../services/';

import { Subscription } from 'rxjs';
import { EntityUtils } from '../../../common/entity/utils';

@Component({
  selector: 'snapshot-rollback',
  templateUrl: './snapshot-rollback.component.html'
})
export class SnapshotRollbackComponent implements OnInit{

  protected resource_name: string = 'storage/snapshot';
  protected route_success: string[] = ['storage', 'snapshots'];
  protected pk: string;


  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected _injector: Injector, protected _appRef: ApplicationRef) {
  }

  ngOnInit() {
    this.route.params.subscribe(params => {
        this.pk = params['pk'];
    });
  }

  doSubmit() {
    let data = {"force": true};

    this.rest.post(this.resource_name + '/' + this.pk + '/rollback/', {
      body: JSON.stringify(data),
    }).subscribe((res) => {
      this.router.navigate(new Array('/pages').concat(this.route_success));
    }, (res) => {
      new EntityUtils().handleError(this, res);
    });
  }

  doCancel() {
    this.router.navigate(new Array('/pages').concat(this.route_success));
  }
}
