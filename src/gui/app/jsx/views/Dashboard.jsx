// Dashboard
// =========
// Default view for FreeNAS, shows overview of system and other general
// information.

"use strict";

import _ from "lodash";
import React from "react";

import ServicesMiddleware from "../middleware/ServicesMiddleware";
import ServicesStore from "../stores/ServicesStore";

import MemoryUtil from "../components/Widgets/MemoryUtil";
import CpuUtil from "../components/Widgets/CpuUtil";
import SystemInfo from "../components/Widgets/SystemInfo";
import SystemLoad from "../components/Widgets/SystemLoad";
import NetworkUsage from "../components/Widgets/NetworkUsage";
import DiskUsage from "../components/Widgets/DiskUsage";

function getServicesFromStore () {
  return {
    servicesList: ServicesStore.getAllServices()
  };
}

const Dashboard = React.createClass({

    getInitialState: function () {
      return getServicesFromStore();
    }

  , componentDidMount: function () {
      ServicesMiddleware.requestServicesList();

      ServicesStore.addChangeListener( this.handleServicesChange );
    }

  , componentWillUnmount: function () {
      ServicesStore.removeChangeListener( this.handleServicesChange );
    }

  , handleServicesChange: function () {
      this.setState( getServicesFromStore() );
    }

  // TODO:
  // Maybe this should be moved into some kind of utility class, and generalized
  , isServiceRunning: function ( service ) {
      return ( _.findIndex( this.state.servicesList, { name: service, state: "running" } ) > -1 );
    }

  , render: function () {
      if ( this.isServiceRunning( "collectd" ) === true ) {
        return (
          <main>
            <div ref="widgetAreaRef" className="widget-wrapper">
              <SystemInfo
                stacked = "true"
                title   = "System Info"
                size    = "m-rect" />
              <MemoryUtil
                title = "Memory Value"
                size  = "m-rect" />
              <CpuUtil
                primary = "pie"
                title = "CPU utilization"
                size  = "m-rect" />
              <SystemLoad
                primary   = "stacked"
                title     = "System Load"
                size      = "m-rect" />
              <NetworkUsage
                title = "Network Usage"
                size  = "l-rect"
                graphType = "line" />
              <DiskUsage
                title = "Disk Usage"
                size  = "l-rect"
                graphType = "line" />
            </div>
          </main>
        );
      } else {
        return (
          <main>
            <h2>Dashboard View</h2>
            <h3>Please enable collectd service to display widgets.</h3>
          </main>
        );
      }
    }

});

export default Dashboard;
