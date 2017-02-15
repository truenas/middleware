import { ModuleWithProviders } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { UserListComponent } from './user-list/';
import { UserAddComponent } from './user-add/';
import { UserEditComponent } from './user-edit/index';
import { UserDeleteComponent } from './user-delete/index';


export const routes: Routes = [
  { path: 'add', component: UserAddComponent },
  { path: 'edit/:pk', component: UserEditComponent },
  { path: 'delete/:pk', component: UserDeleteComponent },
  { path: '', component: UserListComponent, pathMatch: 'full' },
];
export const routing: ModuleWithProviders = RouterModule.forChild(routes);
