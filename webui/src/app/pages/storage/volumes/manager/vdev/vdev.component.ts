import { Component, ElementRef, Input, OnInit, QueryList, ViewChild } from '@angular/core';

import { DiskComponent } from '../disk/';
import { ManagerComponent } from '../manager.component';

@Component({
  selector: 'app-vdev',
  templateUrl: 'vdev.component.html',
  styleUrls: ['vdev.component.css'],
})
export class VdevComponent implements OnInit {

  @Input() group: string;
  @Input() manager: ManagerComponent;
  @ViewChild('dnd') dnd;
  public type: string = 'stripe';
  public removable: boolean = true;
  private diskComponents: Array<DiskComponent> = [];

  constructor(public elementRef: ElementRef) {}

  ngOnInit() {
  }

  addDisk(disk: DiskComponent) {
    this.diskComponents.push(disk);
  }

  removeDisk(disk: DiskComponent) {
    this.diskComponents.splice(this.diskComponents.indexOf(disk), 1);
  }

  getDisks() {
    return this.diskComponents;
  }

  onTypeChange(e) {
    console.log(e, this.group);
  }

  remove() {
    this.manager.removeVdev(this);
  }

}
