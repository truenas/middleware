import { Component, ViewChild } from '@angular/core';

import { WebSocketService } from '../../../services/';
import { ModalDirective } from 'ng2-bootstrap/modal';

@Component({
  selector: 'ba-job',
  styleUrls: ['./baJob.scss'],
  templateUrl: './baJob.html',
})
export class BaJob {

  private job: any;
  private progress: any;

  @ViewChild(ModalDirective) modal: ModalDirective;

  public constructor(private ws: WebSocketService) { }

  public show() {
    this.modal.show();
  }

  public submit() {

    this.ws.job('update.update', []).subscribe(
      (res) => {
        this.job = res;
        this.progress = res.progress;
      },
      () => {},
      () => {
        if(this.job.state == 'SUCCESS') {
        }
      }
    );

  }

}
