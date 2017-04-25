import { Component, Input } from '@angular/core';

import { RestService, WebSocketService } from '../../../services/';

import { Subscription } from 'rxjs';

@Component({
  selector: 'service',
  styleUrls: ['./service.component.scss'],
  template: `
  <ba-card>
    <div [ngBusy]="busy" class="row">
      <div class="col-md-2">
        <span>{{ status.label }}</span>
      </div>

      <div class="col-md-1" [ngClass]="status.state == 'RUNNING' ? 'state-label-running' : 'state-label-stopped'">
        {{status.state}}
      </div>

      <div class="col-md-2">
        <button class="btn btn-primary" (click)="toggle()">
          <i [ngClass]="status.state == 'RUNNING' ? 'ion-stop' : 'ion-power'"></i>
          <span *ngIf="status.state != 'RUNNING'">Start</span>
          <span *ngIf="status.state == 'RUNNING'">Stop</span>
        </button>
      </div>

      <div class="col-md-2">
        <ba-checkbox [(ngModel)]="status.enable" (change)="enableToggle($event)" [label]="'Start on Boot'"></ba-checkbox>
      </div>

      <div class="col-md-1">
        <button class="btn btn-primary">
          <i class="ion-wrench"></i>
          <span>Edit</span>
        </button>
      </div>
    </div>
  </ba-card>
  `,
})
export class Service {

  @Input('status') status: any;

  private busy: Subscription;

  constructor(private rest: RestService, private ws: WebSocketService) {
  }

  toggle() {

    let rpc: string;
    if(this.status.state != 'RUNNING') {
      rpc = 'service.start';
    } else {
      rpc = 'service.stop';
    }

    this.busy = this.ws.call(rpc, [this.status.service]).subscribe((res) => {
      if(res) {
        this.status.state = 'RUNNING';
      } else {
        this.status.state = 'STOPPED';
      }
    });

  }

  enableToggle($event: any) {

    this.busy = this.ws.call('service.update', [this.status.id, { enable: this.status.enable }]).subscribe((res) => {
      if(!res) {
        this.status.enable = !this.status.enable;
      }
    });

  }

}
