import { Routes, RouterModule } from '@angular/router';
import { Pages } from './pages.component';
import { ModuleWithProviders } from '@angular/core';
import { AuthGuard } from './login/auth-guard.service';
// noinspection TypeScriptValidateTypes

// export function loadChildren(path) { return System.import(path); };

export const routes: Routes = [
  {
    path: 'login',
    loadChildren: 'app/pages/login/login.module#LoginModule'
  },
  {
    path: 'pages',
    component: Pages,
    canActivate: [AuthGuard],
    children: [
      { path: 'dashboard', loadChildren: 'app/pages/dashboard/dashboard.module#DashboardModule' },
      { path: 'users', loadChildren: 'app/pages/users/users.module#UsersModule' },
      { path: 'groups', loadChildren: 'app/pages/groups/groups.module#GroupsModule' },
      { path: 'interfaces', loadChildren: 'app/pages/interfaces/interfaces.module#InterfacesModule' },
      { path: 'volumes', loadChildren: 'app/pages/volumes/volumes.module#VolumesModule' },
      { path: 'sharing/afp', loadChildren: 'app/pages/sharing/afp/afp.module#AFPModule' },
      { path: 'sharing/nfs', loadChildren: 'app/pages/sharing/nfs/nfs.module#NFSModule' },
      { path: 'sharing/smb', loadChildren: 'app/pages/sharing/smb/smb.module#SMBModule' },
      { path: 'services', loadChildren: 'app/pages/services/services.module#ServicesModule' },
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
    ]
  },
];

export const routing: ModuleWithProviders = RouterModule.forChild(routes);
