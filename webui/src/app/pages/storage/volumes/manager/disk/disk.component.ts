import { Component, ElementRef, Input, OnInit, Type } from '@angular/core';

import filesize from 'filesize.js';

@Component({
  selector: 'app-disk',
  template: `
  <span>
    {{ data.devname }} ({{ capacity }})
  </span>
  `,
  styles: ['span { float: letf; display:inline-block; margin: 5px; padding: 1px; margin-top: 4px; border: 1px solid #ddd; }'],
})
export class DiskComponent implements OnInit {

  @Input() data: any;
  private capacity: string;

  constructor(public elementRef:ElementRef) {
  }

  ngOnInit() {
    console.log()
    this.capacity = filesize(this.data.capacity, {standard: "si"});
  }

}
