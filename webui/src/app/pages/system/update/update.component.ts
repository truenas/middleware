import { ApplicationRef, Component, Injector, OnInit, ViewContainerRef } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { RestService, WebSocketService } from '../../../services/';

import { Subscription } from 'rxjs';

@Component({
  selector: 'app-update',
  templateUrl: './update.component.html',
})
export class UpdateComponent implements OnInit {

  private packages: any[] = [];
  private status: string;
  private updating: boolean = false;
  private updated: boolean = false;
  private progress: Object = {};
  private job: any = {};

  private busy: Subscription;

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected ws: WebSocketService) {

  }

  ngOnInit() {
  }

  check() {
    this.busy = this.ws.call('update.check_available').subscribe((res) => {
      this.status = res.status;
      if(res.status == 'AVAILABLE') {
        this.packages = [];
        res.changes.forEach((item) => {
          if(item.operation == 'upgrade') {
            this.packages.push({
              name: item.old.name + '-' + item.old.version + ' -> ' + item.new.name + '-' + item.new.version,
            });
          } else if (item.operation == 'install') {
            this.packages.push({
              name: item.new.name + '-' + item.new.version,
            });
          } else {
            this.packages.push({
              name: item.old.name + '-' + item.old.version,
            });
          }
        });
      }
    });
  }

  update() {
    this.updating = true;
    this.ws.job('update.update', []).subscribe(
      (res) => {
        this.job = res;
        this.progress = res.progress;
      },
      () => {},
      () => {
        this.updating = false;
        if(this.job.state == 'SUCCESS') {
          this.updated = true;
        }
      }
    );
  }

}
