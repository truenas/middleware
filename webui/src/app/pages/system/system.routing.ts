import { ModuleWithProviders } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { AdvancedComponent } from './advanced/';
import { EmailComponent } from './email/';
import { GeneralComponent, ConfigSaveComponent, ConfigUploadComponent, ConfigResetComponent } from './general/';
import { UpdateComponent } from './update/';

export const routes: Routes = [
  { path: 'general', component: GeneralComponent },
  { path: 'general/config-save', component: ConfigSaveComponent },
  { path: 'general/config-upload', component: ConfigUploadComponent },
  { path: 'general/config-reset', component: ConfigResetComponent },
  { path: 'email', component: EmailComponent },
  { path: 'advanced', component: AdvancedComponent },
  { path: 'update', component: UpdateComponent },
  { path: 'ntpservers', loadChildren: 'app/pages/system/ntpservers/ntpservers.module#NTPServersModule' },
];
export const routing: ModuleWithProviders = RouterModule.forChild(routes);
