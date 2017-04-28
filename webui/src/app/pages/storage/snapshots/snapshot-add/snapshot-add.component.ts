import { ApplicationRef, Component, Injector, Input, OnInit, QueryList, ViewChildren } from '@angular/core';
import { FormControl, FormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import * as moment from 'moment';
import { DynamicFormControlModel, DynamicFormService, DynamicInputModel, DynamicCheckboxModel } from '@ng2-dynamic-forms/core';

import { GlobalState } from '../../../../global.state';
import { RestService, WebSocketService } from '../../../../services/';

import { Subscription } from 'rxjs';
import { EntityUtils } from '../../../common/entity/utils';

@Component({
  selector: 'snapshot-add',
  templateUrl: './snapshot-add.component.html'
})
export class SnapshotAddComponent implements OnInit{

  protected resource_name: string = 'storage/snapshot';
  protected route_success: string[] = ['storage', 'volumes'];
  protected pk: any;

  protected formModel: DynamicFormControlModel[] = [
    new DynamicInputModel({
      id: 'name',
      label: 'Snapshot Name'
    }),
    new DynamicCheckboxModel({
      id: 'recursive',
      label: 'Recursive'
    })
  ];

  public formGroup: FormGroup;
  public error: string;
  public data: Object = {};
  private busy: Subscription;

  @ViewChildren('component') components;

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected ws: WebSocketService, protected formService: DynamicFormService, protected _injector: Injector, protected _appRef: ApplicationRef, protected _state: GlobalState) {

  }

  ngOnInit() {
    this.route.params.subscribe(params => {
        this.pk = params['pk'];
    });
    let placeholder = this.formService.findById("name", this.formModel) as DynamicInputModel;
    placeholder.valueUpdates.next("manual-" + moment().format('YYYYMMDD'));
    this.formGroup = this.formService.createFormGroup(this.formModel);
  }

  onSubmit() {
    this.error = null;
    let value = this.formGroup.value;
    value['dataset'] = this.pk;
    this.busy = this.rest.post(this.resource_name + '/', {
      body: JSON.stringify(value),
    }).subscribe((res) => {
      this.router.navigate(new Array('/pages').concat(this.route_success));
    }, (res) => {
      new EntityUtils().handleError(this, res);
    });
  }
}
