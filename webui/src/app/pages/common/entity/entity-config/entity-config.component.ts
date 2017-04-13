import { Component, ContentChildren, Input, OnDestroy, OnInit, QueryList, TemplateRef, ViewChildren } from '@angular/core';
import { FormControl, FormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService } from '@ng2-dynamic-forms/core';
import { RestService, WebSocketService } from '../../../../services/';

import { Subscription } from 'rxjs';
import { EntityUtils } from '../utils';
import { EntityTemplateDirective } from '../entity-template.directive';

import * as _ from 'lodash';

@Component({
  selector: 'entity-config',
  templateUrl: './entity-config.component.html',
  styleUrls: []
})
export class EntityConfigComponent implements OnInit, OnDestroy {

  @Input('conf') conf: any;

  protected formGroup: FormGroup;
  templateTop: TemplateRef<any>;
  @ContentChildren(EntityTemplateDirective) templates: QueryList<EntityTemplateDirective>;

  @ViewChildren('component') components;

  private busy: Subscription;

  private sub: any;
  public error: string;
  public success: boolean = false;
  public data: Object = {};

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected ws: WebSocketService, protected formService: DynamicFormService) {

  }

  ngAfterViewInit() {
    this.templates.forEach((item) => {
      if(item.type == 'TOP') {
        this.templateTop = item.templateRef;
      }
    });
  }

  ngOnInit() {
    this.formGroup = this.formService.createFormGroup(this.conf.formModel);
    this.sub = this.route.params.subscribe(params => {
      this.rest.get(this.conf.resource_name + '/', {}).subscribe((res) => {
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

  onSubmit() {
    this.error = null;
    this.success = false;
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

    this.busy = this.rest.put(this.conf.resource_name + '/', {
      body: JSON.stringify(value),
    }).subscribe((res) => {
      if(this.conf.route_success) {
        this.router.navigate(new Array('/pages').concat(this.conf.route_success));
      } else {
        this.success = true;
      }
    }, (res) => {
      new EntityUtils().handleError(this, res);
    });
  }

  ngOnDestroy() {
    this.sub.unsubscribe();
  }

}
