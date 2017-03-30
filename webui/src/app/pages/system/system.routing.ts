import { ModuleWithProviders } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { AdvancedComponent } from './advanced/';
import { GeneralComponent } from './general/';
import { UpdateComponent } from './update/';

export const routes: Routes = [
  { path: 'general', component: GeneralComponent },
  { path: 'advanced', component: AdvancedComponent },
  { path: 'update', component: UpdateComponent },
];
export const routing: ModuleWithProviders = RouterModule.forChild(routes);
