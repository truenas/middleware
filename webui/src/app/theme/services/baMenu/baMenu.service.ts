import {Injectable} from '@angular/core';
import {Router, Routes} from '@angular/router';
import * as _ from 'lodash';

import { BehaviorSubject } from 'rxjs/BehaviorSubject';

@Injectable()
export class BaMenuService {
  menuItems = new BehaviorSubject<any[]>([]);

  protected _currentMenuItem = {};

  constructor(private _router:Router) { }

  /**
   * Updates the routes in the menu
   */
  public updateMenu(menu: any[]) {
    let items = this._convertArrayToItems(menu);
    items = this._skipEmpty(items);
    this.menuItems.next(items);
  }

  public getCurrentItem():any {
    return this._currentMenuItem;
  }

  public selectMenuItem(menuItems:any[], parent?: any):any[] {
    let items = [];
    menuItems.forEach((item) => {
      this._selectItem(item, parent);

      if (item.selected) {
        this._currentMenuItem = item;
      }

      if (item.children && item.children.length > 0) {
        item.children = this.selectMenuItem(item.children, item);
      }
      items.push(item);
    });
    return items;
  }

  protected _skipEmpty(items:any[]):any[] {
    let menu = [];
    items.forEach((item) => {
      let menuItem;
      if (item.skip) {
        if (item.children && item.children.length > 0) {
          menuItem = item.children;
        }
      } else {
        menuItem = item;
      }

      if (menuItem) {
        menu.push(menuItem);
      }
    });

    return [].concat.apply([], menu);
  }

  protected _convertArrayToItems(array:any[], parent?:any):any[] {
    let items = [];
    array.forEach((item) => {
      items.push(this._convertObjectToItem(item, parent));
    });
    return items;
  }

  protected _convertObjectToItem(object, parent?:any):any {
    let item:any = {};
    item = object;

    if (object.children && object.children.length > 0) {
      item.children = this._convertArrayToItems(object.children, item);
    }

    let prepared = item;

    // if current item is selected or expanded - then parent is expanded too
    if ((prepared.selected || prepared.expanded) && parent) {
      parent.expanded = true;
    }

    return prepared;
  }

  protected _selectItem(object:any, parent?: any):any {
    let url = new Array('/pages').concat(object.path);
    object.selected = this._router.isActive(this._router.serializeUrl(this._router.createUrlTree(url)), object.pathMatch === 'full');
    if(object.selected && parent !== undefined) {
      parent.expanded = true;
    }
    return object;
  }
}
