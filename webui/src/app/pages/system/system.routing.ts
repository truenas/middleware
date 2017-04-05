import { ModuleWithProviders } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { AdvancedComponent } from './advanced/';
import { EmailComponent } from './email/';
import { GeneralComponent } from './general/';
import { UpdateComponent } from './update/';

export const routes: Routes = [
  { path: 'general', component: GeneralComponent },
  { path: 'email', component: EmailComponent },
  { path: 'advanced', component: AdvancedComponent },
  { path: 'update', component: UpdateComponent },
];
export const routing: ModuleWithProviders = RouterModule.forChild(routes);
