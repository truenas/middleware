import { ModuleWithProviders } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { VmListComponent } from './vm-list/';
import { VmAddComponent } from './vm-add/';
import { VmEditComponent } from './vm-edit/index';
import { VmDeleteComponent } from './vm-delete/index';


export const routes: Routes = [
  { path: 'add', component: VmAddComponent },
  { path: 'edit/:pk', component: VmEditComponent },
  { path: 'delete/:pk', component: VmDeleteComponent },
  { path: '', component: VmListComponent, pathMatch: 'full' },
];
export const routing: ModuleWithProviders = RouterModule.forChild(routes);
