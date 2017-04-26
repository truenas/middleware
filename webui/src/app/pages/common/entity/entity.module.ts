import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { NgaModule } from '../../../theme/nga.module';
import { DynamicFormsCoreModule } from '@ng2-dynamic-forms/core';
import { DynamicFormsBootstrapUIModule } from '@ng2-dynamic-forms/ui-bootstrap';

import { EntityAddComponent } from './entity-add/entity-add.component';
import { EntityConfigComponent } from './entity-config/entity-config.component';
import { EntityDeleteComponent } from './entity-delete/entity-delete.component';
import { EntityEditComponent } from './entity-edit/entity-edit.component';
import { EntityListComponent } from './entity-list/entity-list.component';
import { EntityListActionsComponent } from './entity-list/entity-list-actions.component';
import { EntityListAddActionsComponent } from './entity-list/entity-list-add-actions.component';
import { EntityTemplateDirective } from './entity-template.directive';
import { RangePipe } from '../../../utils/range.pipe';

import { RestService, WebSocketService } from '../../../services/index';

@NgModule({
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    DynamicFormsCoreModule.forRoot(),
    DynamicFormsBootstrapUIModule,
    NgaModule,
  ],
  declarations: [
    EntityAddComponent,
    EntityConfigComponent,
    EntityDeleteComponent,
    EntityEditComponent,
    EntityListComponent,
    EntityListActionsComponent,
    EntityListAddActionsComponent,
    EntityTemplateDirective,
    RangePipe,
  ],
  exports: [
    EntityAddComponent,
    EntityConfigComponent,
    EntityDeleteComponent,
    EntityEditComponent,
    EntityListComponent,
    EntityTemplateDirective,
  ],
})
export class EntityModule { }
