import { NgModule }      from '@angular/core';
import { CommonModule }  from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { NgaModule } from '../../theme/nga.module';
import { DynamicFormsCoreModule } from '@ng2-dynamic-forms/core';
import { DynamicFormsBootstrapUIModule } from '@ng2-dynamic-forms/ui-bootstrap';

import { EntityModule } from '../common/entity/entity.module';
import { routing }       from './users.routing';

import { UserListComponent } from './user-list/';
import { UserAddComponent } from './user-add/';
import { UserEditComponent } from './user-edit/';
import { UserDeleteComponent } from './user-delete/';

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
    UserListComponent,
    UserAddComponent,
    UserEditComponent,
    UserDeleteComponent,
  ],
  providers: [
  ]
})
export class UsersModule {}
