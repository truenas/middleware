import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { NgaModule } from '../../theme/nga.module';
import { DynamicFormsCoreModule } from '@ng2-dynamic-forms/core';
import { DynamicFormsBootstrapUIModule } from '@ng2-dynamic-forms/ui-bootstrap';

import { EntityModule } from '../common/entity/entity.module';
import { routing } from './system.routing';

import { AdvancedComponent } from './advanced/';
import { EmailComponent } from './email/';
import { GeneralComponent } from './general/';
import { UpdateComponent } from './update/';

@NgModule({
  imports: [
    EntityModule,
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
    EmailComponent,
    GeneralComponent,
    UpdateComponent,
  ],
  providers: [
  ]
})
export class SystemModule { }
