import { NgModule }      from '@angular/core';
import { CommonModule }  from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { NgaModule } from '../../theme/nga.module';
import { DynamicFormsCoreModule } from '@ng2-dynamic-forms/core';
import { DynamicFormsBootstrapUIModule } from '@ng2-dynamic-forms/ui-bootstrap';
import { BusyModule } from 'angular2-busy';

import { EntityModule } from '../common/entity/entity.module';
import { routing }       from './volumes.routing';

import { DragulaModule } from 'ng2-dragula';

import { DatasetAddComponent } from './datasets/dataset-add/';
import { DatasetDeleteComponent } from './datasets/dataset-delete/';
import { VolumesListComponent } from './volumes-list/';
import { ManagerComponent, DiskComponent, VdevComponent } from './manager/';
//import { VolumesEditComponent } from './volumes-edit/';
import { VolumeDeleteComponent } from './volume-delete/';

@NgModule({
  imports: [
    RouterModule,
    DragulaModule,
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
    VolumesListComponent,
    ManagerComponent,
    DiskComponent,
    VdevComponent,
    DatasetAddComponent,
    DatasetDeleteComponent,
    //VolumesEditComponent,
    VolumeDeleteComponent,
  ],
  providers: [
  ]
})
export class VolumesModule {}
