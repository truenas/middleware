// Dashboard
// =========
// Default view for FreeNAS, shows overview of system and other general
// information.

"use strict";

var React = require("react");

var MemoryUtil   = require("../components/Widgets/MemoryUtil");
var CpuUtil      = require("../components/Widgets/CpuUtil");
var SystemInfo   = require("../components/Widgets/SystemInfo");
var SystemLoad   = require("../components/Widgets/SystemLoad");
var NetworkUsage = require("../components/Widgets/NetworkUsage");
var DiskUsage    = require("../components/Widgets/DiskUsage");

var Dashboard = React.createClass({

  render: function() {
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
