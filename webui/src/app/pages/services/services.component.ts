import { Component, OnInit } from '@angular/core';

import { RestService, WebSocketService } from '../../services/';

import { Subscription } from 'rxjs';

@Component({
  selector: 'services',
  styleUrls: ['./services.scss'],
  templateUrl: './services.html'
})
export class Services implements OnInit {

  protected services: any[];
  private busy: Subscription;

  private NAME_MAP: Object = {
    'afp': 'AFP',
    'domaincontroller': 'Domain Controller',
    'dynamicdns': 'Dynamic DNS',
    'ftp': 'FTP',
    'iscsitarget': 'iSCSI',
    'lldp': 'LLDP',
    'nfs': 'NFS',
    'rsync': 'Rsync',
    's3': 'S3',
    'smartd': 'S.M.A.R.T.',
    'snmp': 'SNMP',
    'ssh': 'SSH',
    'cifs': 'SMB',
    'tftp': 'TFTP',
    'ups': 'UPS',
    'webdav': 'WebDAV',
  }

  constructor(protected rest: RestService, protected ws: WebSocketService) {
  }

  ngOnInit() {

    this.busy = this.ws.call('service.query', [[], {"order_by": ["service"]}]).subscribe((res) => {
      this.services = res;
      this.services.forEach((item) => {
        if(this.NAME_MAP[item.service]) {
          item.label = this.NAME_MAP[item.service];
        } else {
          item.label = item.service;
        }
      })
    });

  }


}
