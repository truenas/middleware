import { ModuleWithProviders } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { InterfacesListComponent } from './interfaces-list/';
import { InterfacesAddComponent } from './interfaces-add/';
import { InterfacesEditComponent } from './interfaces-edit/index';
import { InterfacesDeleteComponent } from './interfaces-delete/index';


export const routes: Routes = [
  { path: '', component: InterfacesListComponent },
  { path: 'add', component: InterfacesAddComponent },
  { path: 'edit/:pk', component: InterfacesEditComponent },
  { path: 'delete/:pk', component: InterfacesDeleteComponent },
];
export const routing: ModuleWithProviders = RouterModule.forChild(routes);
