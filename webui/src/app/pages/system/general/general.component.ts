import { ApplicationRef, Component, Injector, OnInit, ViewContainerRef } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { RestService } from '../../../services/rest.service';

@Component({
  selector: 'app-general',
  template: `<entity-config [conf]="this"></entity-config>`
})
export class GeneralComponent {

  protected resource_name: string = 'system/settings';

  protected formModel: DynamicFormControlModel[] = [
    new DynamicSelectModel({
      id: 'stg_guiprotocol',
      label: 'IPv4 Netmask',
      options: [
        { label: 'HTTP', value: 'http' },
        { label: 'HTTPS', value: 'https' },
        { label: 'HTTP+HTTPS', value: 'httphttps' },
      ],
    }),
    new DynamicInputModel({
      id: 'stg_guiaddress',
      label: 'GUI Bind Address',
    }),
    new DynamicInputModel({
      id: 'stg_guiport',
      label: 'GUI HTTP Port',
    }),
    new DynamicInputModel({
      id: 'stg_guihttpsport',
      label: 'GUI HTTPS Port',
    }),
    new DynamicCheckboxModel({
      id: 'stg_guihttpsredirect',
      label: 'GUI HTTP -> HTTPS Redirect',
    }),
  ];

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected formService: DynamicFormService, protected _injector: Injector, protected _appRef: ApplicationRef) {

  }

  afterInit(entityEdit: any) {
  }

}
