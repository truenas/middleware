import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NgaModule } from '../../theme/nga.module';
import { ChartistModule } from 'ng-chartist';

import { Dashboard } from './dashboard.component';
import { LineChart } from './lineChart/lineChart.component';
import { LineChartService } from './lineChart/lineChart.service';
import { routing } from './dashboard.routing';

@NgModule({
  imports: [
    CommonModule,
    ChartistModule,
    FormsModule,
    NgaModule,
    routing
  ],
  declarations: [
    Dashboard,
    LineChart,
  ],
  providers: [
    LineChartService,
  ]
})
export class DashboardModule { }
