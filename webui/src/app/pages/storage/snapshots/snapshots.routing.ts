import { ModuleWithProviders } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { SnapshotListComponent } from './snapshot-list/';
import { SnapshotDeleteComponent } from './snapshot-delete/';


export const routes: Routes = [
  { path: 'delete/:pk', component: SnapshotDeleteComponent },
  { path: '', component: SnapshotListComponent, pathMatch: 'full' },
];
export const routing: ModuleWithProviders = RouterModule.forChild(routes);
