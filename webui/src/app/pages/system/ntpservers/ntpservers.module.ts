import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { NgaModule } from '../../../theme/nga.module';
import { DynamicFormsCoreModule } from '@ng2-dynamic-forms/core';
import { DynamicFormsBootstrapUIModule } from '@ng2-dynamic-forms/ui-bootstrap';

import { EntityModule } from '../../common/entity/entity.module';
import { routing } from './ntpservers.routing';

import { NTPServerListComponent } from './ntpserver-list/';
import { NTPServerAddComponent } from './ntpserver-add/';
import { NTPServerEditComponent } from './ntpserver-edit/';
import { NTPServerDeleteComponent } from './ntpserver-delete/';

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
    NTPServerListComponent,
    NTPServerAddComponent,
    NTPServerEditComponent,
    NTPServerDeleteComponent,
  ],
  providers: [
  ]
})
export class NTPServersModule { }
