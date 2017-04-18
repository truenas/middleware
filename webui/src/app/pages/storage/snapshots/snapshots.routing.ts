import { ModuleWithProviders } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { SnapshotListComponent } from './snapshot-list/';
import { SnapshotAddComponent } from './snapshot-add/';
import { SnapshotDeleteComponent } from './snapshot-delete/';


export const routes: Routes = [
  { path: 'add', component: SnapshotAddComponent },
  { path: 'delete/:pk', component: SnapshotDeleteComponent },
  { path: '', component: SnapshotListComponent, pathMatch: 'full' },
];
export const routing: ModuleWithProviders = RouterModule.forChild(routes);
