"use strict";

var React = require("react");

var Icon   = require("./Icon");


var Widget = React.createClass({
  render: function() {
    return (
      <div className={"widget " + this.props.size}>
        <div className="widget-content">
          { this.props.children }
        </div>
      </div>
    );
  }
});

module.exports = Widget;

      // Widget header removed for now
      //  <header>
      //    <span className="widgetTitle">{this.props.title} <Icon glyph="gear" icoSize="lg" /></span>
      //  </header>