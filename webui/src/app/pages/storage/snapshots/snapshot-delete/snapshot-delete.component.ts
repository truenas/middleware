import { Component } from '@angular/core';

@Component({
  selector: 'app-snapshot-delete',
  template: `<entity-delete [conf]="this"></entity-delete>`
})
export class SnapshotDeleteComponent {

  protected resource_name: string = 'storage/snapshot';
  protected route_success: string[] = ['storage', 'snapshot'];
}
