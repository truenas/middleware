import { Component, Inject, NgZone, ViewChild } from '@angular/core';

import { BaJob } from '../../../../theme/components';
import { RestService, WebSocketService } from '../../../../services/';

import { NgUploaderOptions, NgFileSelectDirective, UploadedFile } from 'ngx-uploader';
import { Subscription, Observable, Observer } from 'rxjs';

@Component({
  selector: 'config-upload',
  templateUrl: 'config-upload.component.html'
})
export class ConfigUploadComponent {

  private options: NgUploaderOptions;
  private busy: Subscription[] = [];
  private sub: Subscription;
  private observer: Observer<any>;
  private jobId: Number;

  @ViewChild(BaJob) baJob: BaJob;
  @ViewChild(NgFileSelectDirective) file: NgFileSelectDirective;

  constructor( @Inject(NgZone) private zone: NgZone, protected ws: WebSocketService) {
    this.options = new NgUploaderOptions({
      url: '/_upload',
      data: {
        data: JSON.stringify({
          method: 'config.upload',
        }),
      },
      autoUpload: false,
      calculateSpeed: true,
      customHeaders: {
        Authorization: 'Basic ' + btoa(ws.username + ':' + ws.password),
      },
    });
  }

  handleUpload(ufile: UploadedFile) {
    if(ufile.done) {
      let resp = JSON.parse(ufile.response);
      this.jobId = resp.job_id;
      this.baJob.jobId = this.jobId;
      this.observer.complete();
      this.baJob.show();
    }
  }

  onSubmit($event) {
    this.sub = Observable.create((observer) => {
      this.observer = observer;
      this.file.uploader.uploadFilesInQueue();
    }).subscribe();
    this.busy.push(this.sub);
  }

  onJobSuccess(job) {
    this.baJob.setDescription('Upload config has completed. Rebooting...')
  }

}