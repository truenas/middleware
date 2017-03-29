import { ModuleWithProviders } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { GeneralComponent } from './general/';

export const routes: Routes = [
  { path: 'general', component: GeneralComponent },
];
export const routing: ModuleWithProviders = RouterModule.forChild(routes);
