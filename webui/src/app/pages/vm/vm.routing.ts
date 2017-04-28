import { ModuleWithProviders } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { VmListComponent } from './vm-list/';
import { VmAddComponent } from './vm-add/';
import { VmEditComponent } from './vm-edit/index';
import { VmDeleteComponent } from './vm-delete/index';
import { DeviceListComponent } from './devices/device-list/';
import { DeviceCdromAddComponent } from './devices/device-cdrom-add/';
import { DeviceNicAddComponent } from './devices/device-nic-add/';
import { DeviceDiskAddComponent } from './devices/device-disk-add/';
import { DeviceVncAddComponent } from './devices/device-vnc-add/';


export const routes: Routes = [
  { path: 'add', component: VmAddComponent },
  { path: 'edit/:pk', component: VmEditComponent },
  { path: 'delete/:pk', component: VmDeleteComponent },
  { path: ':pk/devices/:name', component: DeviceListComponent },
  { path: ':pk/devices/:name/cdrom/add', component: DeviceCdromAddComponent },
  { path: ':pk/devices/:name/disk/add', component: DeviceDiskAddComponent },
  { path: ':pk/devices/:name/nic/add', component: DeviceNicAddComponent },
  { path: ':pk/devices/:name/vnc/add', component: DeviceVncAddComponent },
  { path: '', component: VmListComponent, pathMatch: 'full' },
];
export const routing: ModuleWithProviders = RouterModule.forChild(routes);
