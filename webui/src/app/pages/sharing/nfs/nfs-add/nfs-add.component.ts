import { Component, ViewContainerRef } from '@angular/core';
import { Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService, DynamicCheckboxModel, DynamicInputModel, DynamicSelectModel, DynamicTextAreaModel, DynamicRadioGroupModel } from '@ng2-dynamic-forms/core';
import { GlobalState } from '../../../../global.state';
import { RestService, WebSocketService } from '../../../../services/';

@Component({
  selector: 'app-nfs-add',
  template: `<entity-add [conf]="this"></entity-add>`
})
export class NFSAddComponent {

  protected route_success: string[] = ['sharing', 'nfs'];
  protected resource_name: string = 'sharing/nfs/';

  protected formModel: DynamicFormControlModel[] = [
    new DynamicInputModel({
      id: 'nfs_comment',
      label: 'Comment',
    }),
    new DynamicInputModel({
      id: 'path',
      label: 'Path',
    }),
    new DynamicTextAreaModel({
      id: 'nfs_network',
      label: 'Network',
    }),
    new DynamicTextAreaModel({
      id: 'nfs_hosts',
      label: 'Hosts',
    }),
    new DynamicCheckboxModel({
      id: 'nfs_alldirs',
      label: 'All dirs',
    }),
  ];

  constructor(protected router: Router, protected rest: RestService, protected ws: WebSocketService, protected formService: DynamicFormService, protected _state: GlobalState) {

  }

  afterInit(entityAdd: any) {

  }

  clean(data) {
    data.nfs_paths = [data.path];
    delete data.path;
    return data;
  }

}
