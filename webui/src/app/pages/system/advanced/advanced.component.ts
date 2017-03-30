import { ApplicationRef, Component, Injector, OnInit, ViewContainerRef } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicTextAreaModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { RestService } from '../../../services/rest.service';

@Component({
  selector: 'app-advanced',
  template: `<entity-config [conf]="this"></entity-config>`
})
export class AdvancedComponent {

  protected resource_name: string = 'system/advanced';

  protected formModel: DynamicFormControlModel[] = [
    new DynamicCheckboxModel({
      id: 'adv_consolemenu',
      label: 'Enable Console Menu',
    }),
    new DynamicCheckboxModel({
      id: 'adv_serialconsole',
      label: 'Enable Serial Console',
    }),
    new DynamicSelectModel({
      id: 'adv_serialport',
      label: 'Serial Port',
      options: [],
    }),
    new DynamicSelectModel({
      id: 'adv_serialspeed',
      label: 'Serial Speed',
      options: [
        { label: '9600', value: "9600" },
        { label: '19200', value: "19200" },
        { label: '38400', value: "38400" },
        { label: '57600', value: "57600" },
        { label: '115200', value: "115200" },
      ],
    }),
    new DynamicCheckboxModel({
      id: 'adv_consolescreensaver',
      label: 'Enable Console Screensaver',
    }),
    new DynamicCheckboxModel({
      id: 'adv_powerdaemon',
      label: 'Enable Power Saving Daemon',
    }),
    new DynamicCheckboxModel({
      id: 'adv_debugkernel',
      label: 'Enable Debug Kernel',
    }),
    new DynamicTextAreaModel({
      id: 'adv_motd',
      label: 'MOTD Banner',
    }),
  ];

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected formService: DynamicFormService, protected _injector: Injector, protected _appRef: ApplicationRef) {

  }

  afterInit(entityEdit: any) {
    entityEdit.ws.call('device.get_info', ['SERIAL']).subscribe((res) => {
      let adv_serialport = <DynamicSelectModel<string>> this.formService.findById("adv_serialport", this.formModel);
      res.forEach((item) => {
        adv_serialport.add({ label: item.name + ' (' + item.start + ')', value: item.start });
      });
    });
  }

}
