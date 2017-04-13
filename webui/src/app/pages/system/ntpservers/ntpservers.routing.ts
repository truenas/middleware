import { ModuleWithProviders } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { NTPServerListComponent } from './ntpserver-list/';
import { NTPServerAddComponent } from './ntpserver-add/';
import { NTPServerEditComponent } from './ntpserver-edit/';
import { NTPServerDeleteComponent } from './ntpserver-delete/';


export const routes: Routes = [
  { path: 'add', component: NTPServerAddComponent },
  { path: 'edit/:pk', component: NTPServerEditComponent },
  { path: 'delete/:pk', component: NTPServerDeleteComponent },
  { path: '', component: NTPServerListComponent, pathMatch: 'full' },
];
export const routing: ModuleWithProviders = RouterModule.forChild(routes);
