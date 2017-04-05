import { ApplicationRef, Component, Injector, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { RestService } from '../../../services/rest.service';

@Component({
  selector: 'app-email',
  template: `<entity-config [conf]="this"></entity-config>`
})
export class EmailComponent {

  protected resource_name: string = 'system/email';

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
    new DynamicInputModel({
      id: 'stg_guihttpsport',
      label: 'GUI HTTPS Port',
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

  constructor() {

  }

  afterInit(entityEdit: any) {
  }

}
