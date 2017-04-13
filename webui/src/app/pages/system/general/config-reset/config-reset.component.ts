import { Component } from '@angular/core';

import { RestService, WebSocketService } from '../../../../services/';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel } from '@ng2-dynamic-forms/core';

import { Subscription } from 'rxjs';

@Component({
  selector: 'config-reset',
  template: `
  <alert type="info"><strong>The system will reboot to perform this operation!</strong></alert>
  <p>Are you sure you want to reset configuration?</p>
  <common-form [conf]="this" [busy]="sub" successMessage="Config resetted. Rebooting..." (success)="onSuccess()"></common-form>`
})
export class ConfigResetComponent {

  private sub: Subscription;

  public resource_name: string = 'system/config/factory_restore';
  protected formModel: DynamicFormControlModel[] = [];

  constructor(protected ws: WebSocketService) {

  }

  onSuccess() {
    this.ws.call('system.reboot', [{ delay: 5 }]);
  }

}