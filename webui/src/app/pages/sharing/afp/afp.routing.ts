import { ModuleWithProviders } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { AFPListComponent } from './afp-list/';
import { AFPAddComponent } from './afp-add/';
import { AFPEditComponent } from './afp-edit/index';
import { AFPDeleteComponent } from './afp-delete/index';


export const routes: Routes = [
  { path: '', component: AFPListComponent },
  { path: 'add', component: AFPAddComponent },
  { path: 'edit/:pk', component: AFPEditComponent },
  { path: 'delete/:pk', component: AFPDeleteComponent },
];
export const routing: ModuleWithProviders = RouterModule.forChild(routes);
