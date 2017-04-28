import { NgModule }      from '@angular/core';
import { CommonModule }  from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { NgaModule } from '../../theme/nga.module';
import { DynamicFormsCoreModule } from '@ng2-dynamic-forms/core';
import { DynamicFormsBootstrapUIModule } from '@ng2-dynamic-forms/ui-bootstrap';

import { EntityModule } from '../common/entity/entity.module';
import { routing }       from './vm.routing';

import { DeviceAddComponent } from './devices/device-add/device-add.component';

import { VmListComponent } from './vm-list/';
import { VmAddComponent } from './vm-add/';
import { VmEditComponent } from './vm-edit/';
import { VmDeleteComponent } from './vm-delete/';
import { DeviceListComponent } from './devices/device-list';
import { DeviceCdromAddComponent } from './devices/device-cdrom-add/';
import { DeviceNicAddComponent } from './devices/device-nic-add/';
import { DeviceDiskAddComponent } from './devices/device-disk-add/';
import { DeviceVncAddComponent } from './devices/device-vnc-add/';
import { DeviceDeleteComponent } from './devices/device-delete/';

@NgModule({
  imports: [
    EntityModule,
    DynamicFormsCoreModule.forRoot(),
    DynamicFormsBootstrapUIModule,
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    NgaModule,
    routing
  ],
  declarations: [
    VmListComponent,
    VmAddComponent,
    VmEditComponent,
    VmDeleteComponent,
    DeviceListComponent,
    DeviceCdromAddComponent,
    DeviceAddComponent,
    DeviceNicAddComponent,
    DeviceDiskAddComponent,
    DeviceVncAddComponent,
    DeviceDeleteComponent
  ],
  providers: [
  ]
})
export class VmModule {}
