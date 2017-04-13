import { NgModule }      from '@angular/core';
import { CommonModule }  from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NgaModule } from '../../theme/nga.module';

import { Service } from './components/service.component';
import { Services } from './services.component';
import { routing }       from './services.routing';

@NgModule({
  imports: [
    CommonModule,
    FormsModule,
    NgaModule,
    routing
  ],
  declarations: [
    Service,
    Services,
  ],
  providers: [
  ]
})
export class ServicesModule {}
