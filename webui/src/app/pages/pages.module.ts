import { NgModule }      from '@angular/core';
import { CommonModule }  from '@angular/common';
import { FormsModule }   from '@angular/forms';

import { routing }       from './pages.routing';
import { NgaModule } from '../theme/nga.module';

import { AuthGuard }     from './login/auth-guard.service';
import { Pages } from './pages.component';

import { RestService, WebSocketService } from '../services/index';

@NgModule({
  imports: [
    CommonModule, NgaModule, FormsModule, routing,
  ],
  declarations: [Pages],
  providers: [AuthGuard, WebSocketService, RestService]
})
export class PagesModule { }
