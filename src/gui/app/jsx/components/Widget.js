/** @jsx React.DOM */

"use strict";

var React = require("react");

var Icon   = require("./Icon");


var Widget = React.createClass({
  render: function() {
    var divStyle = {
      position: "absolute",
      left: this.props.positionX + "px",
      top: this.props.positionY + "px"
    };

    return (
      <div className={"widget " + this.props.size} style={divStyle}>
        <header>
          <span className="widgetTitle">{this.props.title} <Icon glyph="gear" icoSize="lg" /></span>
        </header>
        <div className="widgetContent">
          { this.props.children }
        </div>
      </div>
    );
  }
});

module.exports = Widget;