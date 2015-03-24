// Dashboard
// =========
// Default view for FreeNAS, shows overview of system and other general
// information.

"use strict";

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

  , isServiceRunning: function(objectArray, serviceNameToTest) {
    var length = objectArray.length;
    var i = 0;
    if (length < 1)
    {
      return false;
    }
    else
    {
      for (; i < length; i++)
      {
        if  (objectArray[i].name === serviceNameToTest && objectArray[i].state === "running")
        {
          return true;
        }
      }
    }
    return false;
  }
  , render: function() {
    if (this.isServiceRunning(this.state.servicesList, "collectd") === false)
    {
      return (
        <main>
          <h2>Dashboard View</h2>
          <h3>Please enable collectd service to display widgets.</h3>
        </main>
      );
    }
    return (
        <main>
          <h2>Dashboard View</h2>
          <div ref="widgetAreaRef" className="widget-wrapper">
            <SystemInfo
              stacked = "true"
              title   = "System Info"
              size    = "m-rect" />
            <MemoryUtil
              title = "Memory Value"
              size  = "l-rect" />
            <CpuUtil
              primary = "pie"
              title = "Memory Value"
              size  = "l-rect" />
            <SystemLoad
              title     = "System Load"
              size      = "l-rect" />
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
  }

});

module.exports = Dashboard;
