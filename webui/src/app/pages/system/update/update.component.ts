import { ApplicationRef, Component, Injector, OnInit, ViewContainerRef } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { RestService, WebSocketService } from '../../../services/';

@Component({
  selector: 'app-update',
  templateUrl: './update.component.html',
})
export class UpdateComponent implements OnInit {

  private packages: any[] = [];

  constructor(protected router: Router, protected route: ActivatedRoute, protected rest: RestService, protected ws: WebSocketService) {

  }

  ngOnInit() {
    this.ws.call('update.get_pending').subscribe((res) => {
      this.packages = res;
    });
  }

}
