import { NgModule }      from '@angular/core';
import { CommonModule }  from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { NgaModule } from '../../../theme/nga.module';
import { DynamicFormsCoreModule } from '@ng2-dynamic-forms/core';
import { DynamicFormsBootstrapUIModule } from '@ng2-dynamic-forms/ui-bootstrap';

import { EntityModule } from '../../common/entity/entity.module';
import { routing }       from './snapshots.routing';

import { SnapshotListComponent } from './snapshot-list/';
import { SnapshotAddComponent } from './snapshot-add/';
import { SnapshotDeleteComponent } from './snapshot-delete/';

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
    SnapshotListComponent,
    SnapshotAddComponent,
    SnapshotDeleteComponent,
  ],
  providers: [
  ]
})
export class SnapshotsModule {}
