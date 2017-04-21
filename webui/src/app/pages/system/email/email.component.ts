import { ApplicationRef, Component, Injector, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormGroup } from '@angular/forms';
import * as _ from 'lodash';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { GlobalState } from '../../../global.state';
import { RestService, WebSocketService } from '../../../services/';



@Component({
  selector: 'app-email',
  template: `
  <entity-config [conf]="this"></entity-config>
  <button class="btn btn-primary" (click)="sendMail()">Send Test Email</button>
  `
})
export class EmailComponent {

  protected resource_name: string = 'system/email';
  private formGroup: FormGroup;
  /*
  // this is a more generic way to add sent test email button
  // I am not there yet :(
  protected custActions: any[]=[
    {
      "name":"Send Test Mail",
      "function": this.sendMail.bind(this)
    }
  ];
  */
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
    this.formGroup = entityEdit.formGroup;
    this.ws = entityEdit.ws;
  }

  sendMail() :void {
    let value = _.cloneDeep(this.formGroup.value);
    let mailObj = {
        "subject": "This is test email",
        "text": "test test",
    };
    this.ws.call('mail.send', [mailObj]).subscribe((res) => {
      // do success stuff here
      //alert("Hey user it succeeded");
      console.log(res)
    });
  }


}
