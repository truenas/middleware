import { NgModule }      from '@angular/core';
import { CommonModule }  from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { NgaModule } from '../../theme/nga.module';
import { DynamicFormsCoreModule } from '@ng2-dynamic-forms/core';
import { DynamicFormsBootstrapUIModule } from '@ng2-dynamic-forms/ui-bootstrap';

import { EntityModule } from '../common/entity/entity.module';
import { routing }       from './interfaces.routing';

import { InterfacesListComponent } from './interfaces-list/';
import { InterfacesAddComponent } from './interfaces-add/';
import { InterfacesEditComponent } from './interfaces-edit/';
import { InterfacesDeleteComponent } from './interfaces-delete/';

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
    InterfacesListComponent,
    InterfacesAddComponent,
    InterfacesEditComponent,
    InterfacesDeleteComponent,
  ],
  providers: [
  ]
})
export class InterfacesModule {}
