import { ModuleWithProviders } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { SnapshotListComponent } from './snapshot-list/';
import { SnapshotDeleteComponent } from './snapshot-delete/';
import { SnapshotCloneComponent } from './snapshot-clone/';


export const routes: Routes = [
  { path: 'delete/:pk', component: SnapshotDeleteComponent },
  { path: 'clone/:pk', component: SnapshotCloneComponent },
  { path: '', component: SnapshotListComponent, pathMatch: 'full' }
];
export const routing: ModuleWithProviders = RouterModule.forChild(routes);
