import { Component } from '@angular/core';
import { Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { GlobalState } from '../../../global.state';
import { RestService, WebSocketService } from '../../../services/';

@Component({
  selector: 'app-interfaces-add',
  template: `<entity-add [conf]="this"></entity-add>`
})
export class InterfacesAddComponent {

  protected route_success: string[] = ['network', 'interfaces'];
  protected resource_name: string = 'network/interface/';

  protected formModel: DynamicFormControlModel[] = [
    new DynamicInputModel({
      id: 'int_name',
      label: 'Name',
    }),
    new DynamicSelectModel({
      id: 'int_interface',
      label: 'Interface',
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

  private int_interface: DynamicSelectModel<string>;

  constructor(protected router: Router, protected rest: RestService, protected ws: WebSocketService, protected formService: DynamicFormService, protected _state: GlobalState) {

  }

  afterInit(entityAdd: any) {
    entityAdd.ws.call('notifier.choices', ['NICChoices']).subscribe((res) => {
      this.int_interface = <DynamicSelectModel<string>>this.formService.findById("int_interface", this.formModel);
      res.forEach((item) => {
        this.int_interface.add({ label: item[1], value: item[0] });
      });
    });
  }

}
