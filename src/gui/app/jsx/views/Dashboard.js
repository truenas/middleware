/** @jsx React.DOM */

// Dashboard
// =========
// Default view for FreeNAS, shows overview of system and other general
// information.

"use strict";


var React = require("react");

var Widget   = require("../components/Widget");

var Dashboard = React.createClass({
  render: function() {
    return (
      <div>
        <h2>Dashboard View</h2>
        <Widget positionX="0" positionY="200" title="Widget 1" size="large" content="http://upload.wikimedia.org/wikipedia/commons/5/51/Stoned-virus-hexacode.jpg" />
        <Widget positionX="425" positionY="200" title="Widget 2" size="medium" content="http://upload.wikimedia.org/wikipedia/commons/5/51/Stoned-virus-hexacode.jpg" />
        <Widget positionX="700" positionY="200" title="Widget 3" size="small" content="http://upload.wikimedia.org/wikipedia/commons/5/51/Stoned-virus-hexacode.jpg" />
        <Widget positionX="900" positionY="200" title="Widget 4" size="small" content="http://upload.wikimedia.org/wikipedia/commons/5/51/Stoned-virus-hexacode.jpg" />
      </div>
    );
  }
});

module.exports = Dashboard;