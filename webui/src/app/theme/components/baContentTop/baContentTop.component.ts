import {Component} from '@angular/core';

import {GlobalState} from '../../../global.state';

@Component({
  selector: 'ba-content-top',
  styleUrls: ['./baContentTop.scss'],
  templateUrl: './baContentTop.html',
})
export class BaContentTop {

  public activePageTitle:string = '';
  public links: any[] = [];

  constructor(private _state:GlobalState) {
    this._state.subscribe('menu.activeLink', (options) => {
      if (options.title) {
        this.activePageTitle = options.title;
      }
      if (options.links) {
        this.links = options.links;
        if (!options.title) {
	  this.activePageTitle = options.links[options.links.length - 1].title;
	}
      }
    });
  }
}
