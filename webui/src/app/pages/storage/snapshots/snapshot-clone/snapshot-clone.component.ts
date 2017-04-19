import { ApplicationRef, Component, Injector, Input, OnInit, QueryList, ViewChildren } from '@angular/core';
import { FormControl, FormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { DynamicFormControlModel, DynamicFormService, DynamicInputModel } from '@ng2-dynamic-forms/core';

import { GlobalState } from '../../../../global.state';
import { RestService, WebSocketService } from '../../../../services/';

import { Subscription } from 'rxjs';
import { EntityUtils } from '../../../common/entity/utils';

@Component({
  selector: 'snapshot-clone',
  templateUrl: './snapshot-clone.component.html'
})
export class SnapshotCloneComponent implements OnInit{

  protected resource_name: string = 'storage/snapshot';
  protected route_success: string[] = ['storage', 'snapshots'];
  protected pk: any;
  protected skipGet: boolean = true;

  protected formModel: DynamicFormControlModel[] = [
    new DynamicInputModel({
      id: 'name',
      label: 'Name'
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
    // this.formModel[0].valueUpdates.next("Foo");
    this.route.params.subscribe(params => {
        this.pk = params['pk'];
    });
    let placeholder = this.formService.findById("name", this.formModel) as DynamicInputModel;
    placeholder.valueUpdates.next(this.pk.replace("@", "/") + "-clone");
    this.formGroup = this.formService.createFormGroup(this.formModel);
  }

  onSubmit() {
    this.error = null;
    let value = this.formGroup.value;
    this.busy = this.rest.post(this.resource_name + '/' + this.pk + '/clone/', {
      body: JSON.stringify(value),
    }).subscribe((res) => {
      this.router.navigate(new Array('/pages').concat(this.route_success));
    }, (res) => {
      new EntityUtils().handleError(this, res);
    });
  }
}


