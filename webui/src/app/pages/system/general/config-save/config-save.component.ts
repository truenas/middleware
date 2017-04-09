import { Component } from '@angular/core';

import { RestService, WebSocketService } from '../../../../services/';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel } from '@ng2-dynamic-forms/core';

import { Subscription } from 'rxjs';

@Component({
  selector: 'config-save',
  template: `
  <p>Select which options you would llike to export in the config file.</p>
  <common-form [conf]="this" [busy]="sub" successMessage="Redirecting to download. Make sure you have pop up enabled in your browser." (save)="doSubmit($event)"></common-form>`
})
export class ConfigSaveComponent {

  private sub: Subscription;

  protected formModel: DynamicFormControlModel[] = [
    new DynamicCheckboxModel({
      id: 'secretseed',
      label: 'Export Password Secret Seed',
    }),
  ];

  constructor(protected ws: WebSocketService) {

  }

  doSubmit($event) {
    this.sub = this.ws.call('core.download', ['config.save', [$event.data], 'freenas.db']).subscribe((res) => {
      $event.form.success = true;
      window.open(res[1]);
    }, (err) => {
      $event.form.error = err.error;
    });
  }

}