import { NgModule }      from '@angular/core';
import { CommonModule }  from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { NgaModule } from '../../../theme/nga.module';
import { DynamicFormsCoreModule } from '@ng2-dynamic-forms/core';
import { DynamicFormsBootstrapUIModule } from '@ng2-dynamic-forms/ui-bootstrap';
import { BusyModule } from 'angular2-busy';

import { EntityAddComponent } from './entity-add/entity-add.component';
import { EntityConfigComponent } from './entity-config/entity-config.component';
import { EntityDeleteComponent } from './entity-delete/entity-delete.component';
import { EntityEditComponent } from './entity-edit/entity-edit.component';
import { EntityListComponent } from './entity-list/entity-list.component';
import { EntityListActionsComponent } from './entity-list/entity-list-actions.component';
import { RangePipe } from '../../../utils/range.pipe';

import { RestService, WebSocketService } from '../../../services/index';

@NgModule({
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    DynamicFormsCoreModule.forRoot(),
    DynamicFormsBootstrapUIModule,
    BusyModule,
    NgaModule,
  ],
  declarations: [
    EntityAddComponent,
    EntityConfigComponent,
    EntityDeleteComponent,
    EntityEditComponent,
    EntityListComponent,
    EntityListActionsComponent,
    RangePipe,
  ],
  exports: [
    EntityAddComponent,
    EntityConfigComponent,
    EntityDeleteComponent,
    EntityEditComponent,
    EntityListComponent,
  ],
})
export class EntityModule { }
