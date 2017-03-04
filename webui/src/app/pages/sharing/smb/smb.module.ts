import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { NgaModule } from '../../../theme/nga.module';
import { DynamicFormsCoreModule } from '@ng2-dynamic-forms/core';
import { DynamicFormsBootstrapUIModule } from '@ng2-dynamic-forms/ui-bootstrap';
import { BusyModule } from 'angular2-busy';

import { EntityModule } from '../../common/entity/entity.module';
import { routing } from './smb.routing';

import { SMBListComponent } from './smb-list/';
import { SMBAddComponent } from './smb-add/';
import { SMBEditComponent } from './smb-edit/';
import { SMBDeleteComponent } from './smb-delete/';

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
    SMBListComponent,
    SMBAddComponent,
    SMBEditComponent,
    SMBDeleteComponent,
  ],
  providers: [
  ]
})
export class SMBModule { }
