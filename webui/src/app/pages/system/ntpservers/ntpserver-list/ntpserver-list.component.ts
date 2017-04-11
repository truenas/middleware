import { Component } from '@angular/core';

@Component({
  selector: 'app-ntpserver-list',
  template: `<entity-list [conf]="this"></entity-list>`
})
export class NTPServerListComponent {

  protected resource_name: string = 'system/ntpserver';
  protected route_add: string[] = ['system', 'ntpservers', 'add'];
  protected route_edit: string[] = ['system', 'ntpservers', 'edit'];
  protected route_delete: string[] = ['system', 'ntpservers', 'delete'];

  public columns: Array<any> = [
    { title: 'Address', name: 'ntp_address' },
    { title: 'Burst', name: 'ntp_burst' },
    { title: 'IBurst', name: 'ntp_iburst' },
    { title: 'Prefer', name: 'ntp_prefer' },
    { title: 'Min. Poll', name: 'ntp_minpoll' },
    { title: 'Max. Poll', name: 'ntp_maxpoll' },
  ];
  public config: any = {
    paging: true,
    sorting: { columns: this.columns },
  };

}
