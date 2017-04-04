import { ApplicationRef, Component, Injector, OnInit, ViewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { RestService, WebSocketService } from '../../../services/';
import { BaJob } from '../../../theme/components';

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
  private train: string;
  private trains: any[];

  @ViewChild(BaJob) baJob: BaJob;

  private busy: Subscription;
  private busy2: Subscription;

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected ws: WebSocketService) { }

  ngOnInit() {
    this.busy = this.rest.get('system/update', {}).subscribe((res) => {
      this.autoCheck = res.data.upd_autocheck;
      this.train = res.data.upd_train;
    });
    this.busy2 = this.ws.call('update.get_trains').subscribe((res) => {
      console.log(res);
      this.trains = [];
      for(let i in res.trains) {
        this.trains.push({
          name: i
        });
      }
      this.train = res.selected;
    })
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
    this.busy = this.ws.call('update.check_available', [{train: this.train}]).subscribe((res) => {
      this.status = res.status;
      if(res.status == 'AVAILABLE') {
        this.packages = [];
        res.changes.forEach((item) => {
          if(item.operation == 'upgrade') {
            this.packages.push({
              operation: 'Upgrade',
              name: item.old.name + '-' + item.old.version + ' -> ' + item.new.name + '-' + item.new.version,
            });
          } else if (item.operation == 'install') {
            this.packages.push({
              operation: 'Install',
              name: item.new.name + '-' + item.new.version,
            });
          } else if (item.operation == 'delete') {
            // FIXME: For some reason new is populated instead of old?
            if(item.old) {
              this.packages.push({
                operation: 'Delete',
                name: item.old.name + '-' + item.old.version,
              });
            } else if(item.new) {
              this.packages.push({
                operation: 'Delete',
                name: item.new.name + '-' + item.new.version,
              });
            }
          } else {
            console.error("Unknown operation:", item.operation)
          }
        });
      }
    }, (err) => {
      this.error = err.error;
    });
  }

  update() {
    this.baJob.show();
  }

}
