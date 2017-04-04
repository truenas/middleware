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
  private error: string;
  private autoCheck = false;

  private busy: Subscription;

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected ws: WebSocketService) { }

  ngOnInit() {
    this.busy = this.rest.get('system/update', {}).subscribe((res) => {
      this.autoCheck = res.data.upd_autocheck;
    });
  }

  toggleAutoCheck() {
    this.busy = this.rest.put('system/update', {
      body: JSON.stringify({upd_autocheck: !this.autoCheck})
    }).subscribe((res) => {
      // verify auto check
    });
  }

  check() {
    this.error = null;
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
    }, (err) => {
      this.error = err.error;
    });
  }

  update() {
    this.error = null;
    this.updating = true;
    this.ws.job('update.update', []).subscribe(
      (res) => {
        this.job = res;
        this.progress = res.progress;
      },
      () => {},
      () => {
        if(this.job.state == 'SUCCESS') {
          this.updated = true;
        }
      }
    );
  }

}
