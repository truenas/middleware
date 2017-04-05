import { NgModule }      from '@angular/core';
import { CommonModule }  from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { NgaModule } from '../../theme/nga.module';
import { DynamicFormsCoreModule } from '@ng2-dynamic-forms/core';
import { DynamicFormsBootstrapUIModule } from '@ng2-dynamic-forms/ui-bootstrap';

import { EntityModule } from '../common/entity/entity.module';
import { routing }       from './groups.routing';

import { GroupListComponent } from './group-list/';
import { GroupAddComponent } from './group-add/';
import { GroupEditComponent } from './group-edit/';
import { GroupDeleteComponent } from './group-delete/';

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
    GroupListComponent,
    GroupAddComponent,
    GroupEditComponent,
    GroupDeleteComponent,
  ],
  providers: [
  ]
})
export class GroupsModule {}
