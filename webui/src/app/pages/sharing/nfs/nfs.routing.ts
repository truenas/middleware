import { ModuleWithProviders } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { NFSListComponent } from './nfs-list/';
import { NFSAddComponent } from './nfs-add/';
import { NFSEditComponent } from './nfs-edit/index';
import { NFSDeleteComponent } from './nfs-delete/index';


export const routes: Routes = [
  { path: '', component: NFSListComponent },
  { path: 'add', component: NFSAddComponent },
  { path: 'edit/:pk', component: NFSEditComponent },
  { path: 'delete/:pk', component: NFSDeleteComponent },
];
export const routing: ModuleWithProviders = RouterModule.forChild(routes);
