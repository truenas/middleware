import { Component, ContentChildren, EventEmitter, Input, OnDestroy, OnInit, Output, QueryList, TemplateRef, ViewChildren } from '@angular/core';
import { FormControl, FormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { DynamicFormControlModel, DynamicFormService } from '@ng2-dynamic-forms/core';
import { RestService, WebSocketService } from '../../../services/';

import { Subscription } from 'rxjs';
import { EntityUtils } from '../entity/utils';
import { EntityTemplateDirective } from '../entity/entity-template.directive';

import * as _ from 'lodash';

@Component({
  selector: 'common-form',
  templateUrl: './form.component.html',
  styleUrls: []
})
export class CommonFormComponent implements OnInit, OnDestroy {

  @Input('conf') conf: any;
  @Input('busy') parentBusy: any = null;
  @Input() successMessage: string = 'Form has been successfully submitted.';

  @Output() save = new EventEmitter();
  @Output('success') successEvent = new EventEmitter();

  templateTop: TemplateRef<any>;
  @ContentChildren(EntityTemplateDirective) templates: QueryList<EntityTemplateDirective>;

  @ViewChildren('component') components;

  protected formGroup: FormGroup;
  public error: string;
  public success: boolean = false;
  private busy: Subscription;

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected ws: WebSocketService, protected formService: DynamicFormService) {

  }

  ngOnInit() {
    this.formGroup = this.formService.createFormGroup(this.conf.formModel);
    if(this.conf.afterInit) {
      this.conf.afterInit(this);
    }
  }

  ngAfterViewInit() {
    this.templates.forEach((item) => {
      if(item.type == 'TOP') {
        this.templateTop = item.templateRef;
      }
    });
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

    /*
      If there is a resource name then we use the common REST path
    */
    if(this.conf.resource_name) {

      this.busy = this.rest.post(this.conf.resource_name + '/', {
        body: JSON.stringify(value),
      }).subscribe((res) => {
        if(this.conf.route_success) {
          this.router.navigate(new Array('/pages').concat(this.conf.route_success));
        } else {
          this.success = true;
          this.successEvent.emit();
        }
      }, (res) => {
        new EntityUtils().handleError(this, res);
      });

    } else {
      this.save.emit({ form: this, data: value });
    }
  }

  ngOnDestroy() {
  }

}
