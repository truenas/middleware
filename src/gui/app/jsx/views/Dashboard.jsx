// Dashboard
// =========
// Default view for FreeNAS, shows overview of system and other general
// information.

"use strict";

var _     = require("lodash");
var React = require("react");

var ServicesMiddleware = require("../middleware/ServicesMiddleware");
var ServicesStore      = require("../stores/ServicesStore");

var MemoryUtil   = require("../components/Widgets/MemoryUtil");
var CpuUtil      = require("../components/Widgets/CpuUtil");
var SystemInfo   = require("../components/Widgets/SystemInfo");
var SystemLoad   = require("../components/Widgets/SystemLoad");
var NetworkUsage = require("../components/Widgets/NetworkUsage");
var DiskUsage    = require("../components/Widgets/DiskUsage");

function getServicesFromStore() {
  return {
    servicesList: ServicesStore.getAllServices()
  };
}

var Dashboard = React.createClass({

    getInitialState: function() {
      return getServicesFromStore();
    }

  , componentDidMount: function() {
      ServicesMiddleware.requestServicesList();

      ServicesStore.addChangeListener( this.handleServicesChange );
    }

  , componentWillUnmount: function() {
      ServicesStore.removeChangeListener( this.handleServicesChange );
    }

  , handleServicesChange: function() {
      this.setState( getServicesFromStore() );
    }

  // TODO: Maybe this should be moved into some kind of utility class, and generalized
  , isServiceRunning: function( service ) {
      return ( _.findIndex( this.state.servicesList, { name: service, state: "running" } ) > -1 );
    }

  , render: function() {
      if (this.isServiceRunning("collectd") === true)
      {
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

module.exports = Dashboard;
