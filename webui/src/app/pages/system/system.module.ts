import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { NgaModule } from '../../theme/nga.module';
import { DynamicFormsCoreModule } from '@ng2-dynamic-forms/core';
import { DynamicFormsBootstrapUIModule } from '@ng2-dynamic-forms/ui-bootstrap';
import { BusyModule } from 'angular2-busy';

import { EntityModule } from '../common/entity/entity.module';
import { routing } from './system.routing';

import { AdvancedComponent } from './advanced/';
import { GeneralComponent } from './general/';
import { UpdateComponent } from './update/';

@NgModule({
  imports: [
    EntityModule,
    BusyModule,
    DynamicFormsCoreModule.forRoot(),
    DynamicFormsBootstrapUIModule,
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    NgaModule,
    routing
  ],
  declarations: [
    AdvancedComponent,
    GeneralComponent,
    UpdateComponent,
  ],
  providers: [
  ]
})
export class SystemModule { }
