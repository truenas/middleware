import {Injectable} from '@angular/core';
import {BaThemeConfigProvider, colorHelper, layoutPaths} from '../../../theme';

import { WebSocketService } from '../../../services/';

@Injectable()
export class LineChartService {

  constructor(private _baConfig:BaThemeConfigProvider, private _ws: WebSocketService) {
  }

  getData(chart: any, dataList: any[]) {

    this._ws.call('stats.get_data', [ dataList, {} ]).subscribe((res) => {
      dataList.forEach(() => { chart.data.series.push([]); })
      res.data.forEach((item, i) => {
        chart.data.labels.push(new Date(res.meta.start * 1000 + i * res.meta.step * 1000));
        for(let x in dataList) {
          chart.data.series[x].push(item[x]);
        }
      });

    });
  }
}
