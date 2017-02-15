import { Routes, RouterModule }  from '@angular/router';

import { Dashboard } from './dashboard.component';
import { ModuleWithProviders } from '@angular/core';

// noinspection TypeScriptValidateTypes
export const routes: Routes = [
  {
    path: '', pathMatch: 'full',
    component: Dashboard,
  }
];

export const routing: ModuleWithProviders = RouterModule.forChild(routes);
