import { ApplicationRef, Component, Injector, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import * as _ from 'lodash';
import { Subscription } from 'rxjs';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { GlobalState } from '../../../global.state';
import { RestService, WebSocketService } from '../../../services/';
import { EntityConfigComponent } from '../../common/entity/entity-config/';



@Component({
  selector: 'app-email',
  template: `
  <entity-config [conf]="this"></entity-config>
  <button class="btn btn-primary" (click)="sendMail()" [ngBusy]="sendEmailBusy">Send Test Email</button>
  `
})
export class EmailComponent {

  protected resource_name: string = 'system/email';
  private entityEdit: EntityConfigComponent;
  private sendEmailBusy: Subscription;
  protected formModel: DynamicFormControlModel[] = [
    new DynamicInputModel({
      id: 'em_fromemail',
      label: 'From E-mail',
    }),
    new DynamicInputModel({
      id: 'em_outgoingserver',
      label: 'Outgoing Mail Server',
    }),
    new DynamicInputModel({
      id: 'em_port',
      label: 'Mail Server Port',
    }),
    new DynamicSelectModel({
      id: 'em_security',
      label: 'Security',
      options: [
        { label: 'Plain', value: 'plain' },
        { label: 'SSL', value: 'ssl' },
        { label: 'TLS', value: 'tls' },
      ],
    }),
    new DynamicCheckboxModel({
      id: 'em_smtp',
      label: 'SMTP Authentication',
    }),
    new DynamicInputModel({
      id: 'em_user',
      label: 'Username',
      relation: [
        {
          action: 'DISABLE',
          when: [
            {
              id: 'em_smtp',
              value: false,
            }
          ]
        },
      ],
    }),
    new DynamicInputModel({
      id: 'em_pass1',
      label: 'Password',
      relation: [
        {
          action: 'DISABLE',
          when: [
            {
              id: 'em_smtp',
              value: false,
            }
          ]
        },
      ],
    }),
    new DynamicInputModel({
      id: 'em_pass2',
      label: 'Confirm Password',
      relation: [
        {
          action: 'DISABLE',
          when: [
            {
              id: 'em_smtp',
              value: false,
            }
          ]
        },
      ],
    }),
  ];

  constructor(protected router: Router, protected rest: RestService, protected ws: WebSocketService, protected formService: DynamicFormService, protected _injector: Injector, protected _appRef: ApplicationRef, protected _state: GlobalState) {

  }

  afterInit(entityEdit: any) {
    this.entityEdit = entityEdit;
  }

  sendMail() :void {
    let value = _.cloneDeep(this.entityEdit.formGroup.value);
    let mailObj = {
        "subject": "Test message from FreeNAS",
        "text": "This is a test message from FreeNAS",
    };
    // TODO fix callback Hell!!
    this.sendEmailBusy = this.ws.call('system.info').subscribe((res)=>{
      mailObj['subject'] += " hostname: " + res['hostname'];
      this.ws.call('mail.send', [mailObj]).subscribe((res) => {
        if (res[0]) {
          this.entityEdit.error = res[1];
        } else {
          this.entityEdit.error = "";
          alert("Test email sent successfully!");
        }
      });
    });
  }

}
