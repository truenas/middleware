import { Component, EventEmitter, HostListener, Input, Output, ViewChild } from '@angular/core';

import { WebSocketService } from '../../../services/';
import { ModalDirective } from 'ng2-bootstrap/modal';
import { ProgressbarComponent } from 'ng2-bootstrap/progressbar';

@Component({
  selector: 'ba-job',
  styleUrls: ['./baJob.scss'],
  templateUrl: './baJob.html',
})
export class BaJob {

  private job: any = {};
  private progressTotalPercent: number = 0;
  private description: string;
  private method: string;
  private args: any[] = [];
  @Input() title: string = '';

  @Output() progress = new EventEmitter();
  @Output() success = new EventEmitter();
  @Output() failure = new EventEmitter();

  @ViewChild(ModalDirective) modal: ModalDirective;
  @ViewChild(ProgressbarComponent) progressbar: ProgressbarComponent;

  public constructor(private ws: WebSocketService) { }

  setCall(method: string, args?: any[]) {
    this.method = method;
    if(args) {
      this.args = args;
    }
  }

  @HostListener('progress', ['$event'])
  public onProgress(progress) {
    if(progress.description) {
      this.description = progress.description;
    }
    if(progress.percent) {
      this.progressTotalPercent = progress.percent;
    }
  }

  public show() {
    this.modal.show();
  }

  public submit() {
    this.show();
    this.ws.job(this.method, this.args).subscribe(
      (res) => {
        this.job = res;
        if(res.progress) {
          this.progress.emit(res.progress);
        }
      },
      () => {},
      () => {
        if(this.job.state == 'SUCCESS') {
          this.failure.emit(this.job);
        } else if(this.job.state == 'FAILED') {
          this.success.emit(this.job);
        }
      }
    );

  }

}
