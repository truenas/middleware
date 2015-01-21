/** @jsx React.DOM */

// Dashboard
// =========
// Default view for FreeNAS, shows overview of system and other general
// information.

"use strict";


var React 		        = 	require("react");

var Widget   	        = 	require("../components/Widget");
var DummyWidgetContent 	= 	require("../components/Widgets/DummyWidgetContent");
var DriveInfo 	        = 	require("../components/Widgets/DriveInfo");
var DriveInfo2 	        = 	require("../components/Widgets/DriveInfo2");
var ProcessesPie 	    = 	require("../components/Widgets/ProcessesPie");


var Dashboard = React.createClass({
  componentDidMount: function() {
  },

  render: function() {
    return (
      <main>
        <h2>Dashboard View</h2>
        <div ref="widgetAreaRef" className="widget-wrapper">
          <DummyWidgetContent positionX="375" positionY="100" title="Dummy Widget" size="small" />
          <DriveInfo positionX="375" positionY="280" title="Drive Info 1" size="small" sn="WC-C4NFLDU8RP" />
          <DriveInfo2 positionX="555" positionY="100" title="Drive Info 2" size="small" sn="WC-AWZ0927810" />
          <ProcessesPie positionX="15" positionY="100" title="Processes Pie" size="medium" />
        </div>
      </main>
    );
  }
});

module.exports = Dashboard;