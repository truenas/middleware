import { Routes, RouterModule }  from '@angular/router';

import { Services } from './services.component';
import { ModuleWithProviders } from '@angular/core';

// noinspection TypeScriptValidateTypes
export const routes: Routes = [
  {
    path: '', pathMatch: 'full',
    component: Services,
  }
];

export const routing: ModuleWithProviders = RouterModule.forChild(routes);
