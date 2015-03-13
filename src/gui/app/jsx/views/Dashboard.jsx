// Dashboard
// =========
// Default view for FreeNAS, shows overview of system and other general
// information.

"use strict";


var React 		         = 	require("react");

var Widget   	         = 	require("../components/Widget");
var MemoryUtil         = 	require("../components/Widgets/MemoryUtil");
var SystemInfo         =  require("../components/Widgets/SystemInfo");
var NetworkUsage       =  require("../components/Widgets/NetworkUsage");

var DriveInfo 	       = 	require("../components/Widgets/DriveInfo");
var DriveInfo2 	       = 	require("../components/Widgets/DriveInfo2");
var ProcessesPie 	     = 	require("../components/Widgets/ProcessesPie");
var SwapUsage 	       = 	require("../components/Widgets/SwapUsage");
var NetworkChart 	     = 	require("../components/Widgets/NetworkChart");
var PoolIOs 		       = 	require("../components/Widgets/PoolIOs");

var Dashboard = React.createClass({
  componentDidMount: function() {
  },

  render: function() {
    return (
      <main>
        <h2>Dashboard View</h2>
        <div ref="widgetAreaRef" className="widget-wrapper">
          <MemoryUtil
            title = "Memory Value"
            size  = "l-rect" />
          <MemoryUtil
            graphType = "stacked"
            title     = "Stacked Memory Value"
            size      = "l-rect" />
          <SystemInfo
            stacked = "true"
            title   = "System Info"
            size    = "m-rect" />
          <NetworkUsage
            title = "Network Usage"
            size  = "l-rect" />
        </div>
      </main>
    );
  }
});

module.exports = Dashboard;


//Dead Widgets
//          <DriveInfo positionX="375" positionY="100" title="Drive Info 1" size="s-square" sn="WC-C4NFLDU8RP" />
//          <DriveInfo2 positionX="555" positionY="100" title="Drive Info 2a" size="s-square" diskData={{sn:"WC-AWZ0927810", name:"da2", size:"6 TB"}} />
//          <DriveInfo2 positionX="735" positionY="820" title="Drive Info 2b" size="s-square" diskData={{sn:"SSD-0543TG812", name:"da3", size:"1 TB", type:"ssd"}} />
//          <ProcessesPie positionX="15" positionY="100" title="Processes Pie" size="l-square" />
//          <SwapUsage positionX="375" positionY="280" title="Swap Usage" size="sl-rect" />
//          <NetworkChart positionX="15" positionY="1000" title="Networ Chart" size="xl-rect" />
//          <PoolIOs positionX="15" positionY="460" title="Pool IOs" size="xl-rect" />

