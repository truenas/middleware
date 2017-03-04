import { ApplicationRef, Component, Injector, Input, OnDestroy, OnInit, ViewChildren } from '@angular/core';
import { FormControl, FormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService } from '@ng2-dynamic-forms/core';
import { RestService, WebSocketService } from '../../../../services/';

import { Subscription } from 'rxjs';
import { EntityUtils } from '../utils';

import * as _ from 'lodash';

@Component({
  selector: 'entity-edit',
  templateUrl: './entity-edit.component.html',
  styleUrls: ['./entity-edit.component.css']
})
export class EntityEditComponent implements OnInit, OnDestroy {

  @Input('conf') conf: any;

  protected pk: any;
  protected formGroup: FormGroup;

  @ViewChildren('component') components;

  private busy: Subscription;

  private sub: any;
  public error: string;
  public data: Object = {};

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected ws: WebSocketService, protected formService: DynamicFormService, protected _injector: Injector, protected _appRef: ApplicationRef) {

  }

  ngOnInit() {
    this.formGroup = this.formService.createFormGroup(this.conf.formModel);
    this.sub = this.route.params.subscribe(params => {
      this.pk = params['pk'];
      this.rest.get(this.conf.resource_name + '/' + this.pk + '/', {}).subscribe((res) => {
        this.data = res.data;
        for(let i in this.data) {
          let fg = this.formGroup.controls[i];
          if(fg) {
            fg.setValue(this.data[i]);
          }
        }
        if(this.conf.initial) {
          this.conf.initial.bind(this.conf)(this);
        }
      })
    });
    this.conf.afterInit(this);
  }

  gotoDelete() {
    this.router.navigate(new Array('/pages').concat(this.conf.route_delete).concat(this.pk));
  }

  onSubmit() {
    this.error = null;
    let value = _.cloneDeep(this.formGroup.value);
    for(let i in value) {
      let clean = this['clean_' + i];
      if(clean) {
        value = clean(value, i);
      }
    }
    if('id' in value) {
      delete value['id'];
    }

    if(this.conf.clean) {
      value = this.conf.clean.bind(this.conf)(value);
    }

    this.busy = this.rest.put(this.conf.resource_name + '/' + this.pk + '/', {
      body: JSON.stringify(value),
    }).subscribe((res) => {
      this.router.navigate(new Array('/pages').concat(this.conf.route_success));
    }, (res) => {
      new EntityUtils().handleError(this, res);
    });
  }

  ngOnDestroy() {
    this.sub.unsubscribe();
  }

}
