import { Component, Input, OnInit, ElementRef } from '@angular/core';
import { Router } from '@angular/router';

import { GlobalState } from '../../../../global.state';
import { RestService } from '../../../../services/rest.service';

import { Subscription } from 'rxjs';

@Component({
  selector: 'entity-list',
  templateUrl: './entity-list.component.html',
  styleUrls: ['./entity-list.component.css']
})
export class EntityListComponent implements OnInit {

  @Input('conf') conf: any;

  private busy: Subscription;

  public rows: Array<any> = [];
  public columns: Array<any> = [];
  public page: number = 1;
  public itemsPerPage: number = 10;
  public maxSize: number = 5;
  public numPages: number = 1;
  public length: number = 0;
  public config: any = {
    paging: true,
    sorting: { columns: this.columns },
  };

  constructor(protected rest: RestService, protected router: Router, protected _state: GlobalState, protected _eRef: ElementRef) { }

  ngOnInit() {
    this.getData();
    if (this.conf.afterInit) {
        this.conf.afterInit(this);
    }
  }

  getData() {
    let offset = this.itemsPerPage * (this.page - 1)
    let sort: Array<String> = [];
    let options: Object = new Object();

    for (let i in this.config.sorting.columns) {
      let col = this.config.sorting.columns[i];
      if (col.sort == 'asc') {
        sort.push(col.name);
      } else if (col.sort == 'desc') {
        sort.push('-' + col.name);
      }
    }

    //options = {limit: this.itemsPerPage, offset: offset};
    options = { limit: 0 };
    if (sort.length > 0) {
      options['sort'] = sort.join(',');
    }

    this.busy = this.rest.get(this.conf.resource_name, options).subscribe((res) => {
      this.length = res.total;
      this.rows = this.flattenData(res.data);
    });
  }

  flattenData(data, level = 0, parent?: any) {
    let ndata = [];
    data.forEach((item) => {
      item._level = level;
      if (parent) {
        item._parent = parent.id;
      }
      ndata.push(item);
      if (item.children) {
        ndata = ndata.concat(this.flattenData(item.children, level + 1, item));
      }
      delete item.children;
    });
    return ndata;
  }

  onChangeTable(config, page: any = { page: this.page, itemsPerPage: this.itemsPerPage }) {
    if (config.filtering) {
      Object.assign(this.config.filtering, config.filtering);
    }
    if (config.sorting) {
      Object.assign(this.config.sorting, config.sorting);
    }
    this.page = page.page;
    this.getData();
  }

  trClass(row) {
    let classes = [];
    classes.push('treegrid-' + row.id);
    if (row._parent) {
      classes.push('treegrid-parent-' + row._parent);
    }
    return classes.join(' ');
  }

  getActions(row) {
    if (this.conf.getActions) {
      return this.conf.getActions(row);
    } else {
      return [
        {
          id: "edit",
          label: "Edit",
          onClick: (row) => {
            this.doEdit(row.id);
          },
        },
        {
          id: "delete",
          label: "Delete",
          onClick: (row) => {
            this.doDelete(row.id);
          },
        },
      ]
    }
  }

  getAddActions() {
    if (this.conf.getAddActions) {
      return this.conf.getAddActions();
    } else {
      return [];
    }
  }

  rowValue(row, attr) {
    if (this.conf.rowValue) {
      return this.conf.rowValue(row, attr);
    }
    return row[attr];
  }

  doAdd() {
    this.router.navigate(new Array('/pages').concat(this.conf.route_add));
  }

  doEdit(id) {
    this.router.navigate(new Array('/pages').concat(this.conf.route_edit).concat(id));
  }

  doDelete(id) {
    this.router.navigate(new Array('/pages').concat(this.conf.route_delete).concat(id));
  }

}
