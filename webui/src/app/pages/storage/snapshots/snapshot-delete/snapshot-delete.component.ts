import { Component } from '@angular/core';

@Component({
  selector: 'app-snapshot-delete',
  template: `<entity-delete [conf]="this"></entity-delete>`
})
export class SnapshotDeleteComponent {

  protected pk: any;
  protected path: string;
  //protected resource_name: string = 'storage/snapshot';
  protected route_success: string[] = ['snapshot'];
  get resource_name(): string {
    return 'storage/snapshot/' + this.pk;
  }

  getPK(entityDelete, params) {
    this.pk = params['pk'];
    this.path = params['path'];
    debugger;
    entityDelete.pk = this.path.split('/').splice(1).join('/');
  }
}
