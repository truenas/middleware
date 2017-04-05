import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { NgaModule } from '../../../theme/nga.module';
import { DynamicFormsCoreModule } from '@ng2-dynamic-forms/core';
import { DynamicFormsBootstrapUIModule } from '@ng2-dynamic-forms/ui-bootstrap';

import { EntityModule } from '../../common/entity/entity.module';
import { routing } from './afp.routing';

import { AFPListComponent } from './afp-list/';
import { AFPAddComponent } from './afp-add/';
import { AFPEditComponent } from './afp-edit/';
import { AFPDeleteComponent } from './afp-delete/';

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
    AFPListComponent,
    AFPAddComponent,
    AFPEditComponent,
    AFPDeleteComponent,
  ],
  providers: [
  ]
})
export class AFPModule { }
