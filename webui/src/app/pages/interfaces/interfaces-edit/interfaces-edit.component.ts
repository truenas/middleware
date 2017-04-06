import { Component } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { RestService } from '../../../services/rest.service';

@Component({
  selector: 'app-interfaces-edit',
  template: `<entity-edit [conf]="this"></entity-edit>`
})
export class InterfacesEditComponent {

  protected resource_name: string = 'network/interface/';
  protected route_delete: string[] = ['network', 'interfaces', 'delete'];
  protected route_success: string[] = ['network', 'interfaces'];

  protected formModel: DynamicFormControlModel[] = [
    new DynamicInputModel({
      id: 'int_name',
      label: 'Name',
    }),
    new DynamicInputModel({
      id: 'int_interface',
      label: 'Interface',
      readOnly: true,
    }),
    new DynamicInputModel({
      id: 'int_ipv4address',
      label: 'IPv4 Address',
      relation: [
        {
          action: "DISABLE",
          when: [
            {
              id: "int_dhcp",
              value: true,
            }
          ]
        },
      ],
    }),
    new DynamicSelectModel({
      id: 'int_v4netmaskbit',
      label: 'IPv4 Netmask',
      options: Array(32).fill(0).map((x, i) => { return { label: String(32 - i), value: String(32 - i) }; }),
      relation: [
        {
          action: "DISABLE",
          when: [
            {
              id: "int_dhcp",
              value: true,
            }
          ]
        },
      ],
    }),
    new DynamicCheckboxModel({
      id: 'int_dhcp',
      label: 'DHCP',
    }),
    new DynamicInputModel({
      id: 'int_options',
      label: 'Options',
    }),
  ];

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected formService: DynamicFormService) {

  }

  afterInit(entityEdit: any) {
  }

}
