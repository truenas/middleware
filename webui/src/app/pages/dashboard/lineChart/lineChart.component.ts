import { Component, Input, OnInit } from '@angular/core';

import { LineChartService } from './lineChart.service';

import 'style-loader!./lineChart.scss';
import filesize from 'filesize.js';
import * as Chartist from 'chartist';

declare var ChartistLegend: any;

@Component({
  selector: 'line-chart',
  templateUrl: './lineChart.html'
})
export class LineChart implements OnInit {

  chartData: Object;

  @Input() dataList: any[];
  @Input() series: any;
  @Input() legends: any[];
  @Input() type: string;

  data = {
      labels: [],
      series: [],
  };

  options: any = {
    showPoint: false,
    axisX: {
      labelInterpolationFnc: function(value, index) {
        let pad = (num, size) => {
          var s = num+"";
          while (s.length < size) s = "0" + s;
          return s;
        }
        //let date = String(value.getYear() + 1900) + '-' + value.getMonth() + '-' + value.getDay() + ' ' + value.getHours() + ':' + value.getMinutes() + ':' + value.getSeconds();
        let date = pad(value.getHours(), 2) + ':' + pad(value.getMinutes(), 2) + ':' + pad(value.getSeconds(), 2);
        return index % 40 === 0 ? date : null;
      },
    },
    axisY: {},
    plugins: []
  };
  reverseOptions = {};

  constructor(private _lineChartService: LineChartService) {
  }

  ngOnInit() {
    if(this.type == 'Pie') {
      delete this.options.axisX;
      delete this.options.axisY;
      this.options.labelInterpolationFnc = function(value, index) {
        // FIXME, workaround to work with just size pie
        return filesize(value);
      }
    }
    if(this.legends && this.type != 'Pie') {
      this.options.plugins.push(
        ChartistLegend({
          classNames: Array(this.legends.length).fill(0).map((x, i) => { return 'ct-series-' + String.fromCharCode(97+i)}),
          legendNames: this.legends,
        })
      );
    }
    if(this.dataList.length > 0) {
      this._lineChartService.getData(this, this.dataList);
    }
    if(this.series) {
      this.series.forEach((i) => {
        this.data.series.push(i);
      });
    }
  }

}
