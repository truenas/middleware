import { ModuleWithProviders } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { VolumesListComponent } from './volumes-list/';
import { DatasetAddComponent } from './datasets/dataset-add/';
import { DatasetDeleteComponent } from './datasets/dataset-delete/';
import { ManagerComponent } from './manager/';
//import { VolumesEditComponent } from './volumes-edit/index';
import { VolumeDeleteComponent } from './volume-delete/index';


export const routes: Routes = [
  { path: '', component: VolumesListComponent },
  { path: 'id/:pk/dataset/add/:path', component: DatasetAddComponent },
  { path: 'id/:pk/dataset/delete/:path', component: DatasetDeleteComponent },
  { path: 'manager', component: ManagerComponent },
  //{ path: 'edit/:pk', component: VolumesEditComponent },
  { path: 'delete/:pk', component: VolumeDeleteComponent },
];
export const routing: ModuleWithProviders = RouterModule.forChild(routes);
