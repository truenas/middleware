import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { NgaModule } from '../../../theme/nga.module';
import { DynamicFormsCoreModule } from '@ng2-dynamic-forms/core';
import { DynamicFormsBootstrapUIModule } from '@ng2-dynamic-forms/ui-bootstrap';
import { BusyModule } from 'angular2-busy';

import { EntityModule } from '../../common/entity/entity.module';
import { routing } from './nfs.routing';

import { NFSListComponent } from './nfs-list/';
import { NFSAddComponent } from './nfs-add/';
import { NFSEditComponent } from './nfs-edit/';
import { NFSDeleteComponent } from './nfs-delete/';

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
    NFSListComponent,
    NFSAddComponent,
    NFSEditComponent,
    NFSDeleteComponent,
  ],
  providers: [
  ]
})
export class NFSModule { }
