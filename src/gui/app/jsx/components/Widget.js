/** @jsx React.DOM */

"use strict";

var React = require("react");

var Icon   = require("./Icon");
var DriveInfo = require("./Widgets/DriveInfo");
var DriveInfo2 = require("./Widgets/DriveInfo2");

var Widget = React.createClass({
  render: function() {
    var divStyle = {
      position: "absolute",
      left: this.props.positionX + "px",
      top: this.props.positionY + "px"
    };
    var wc = <img src={this.props.content} />;

    if ( this.props.content === "driveInfo1" ){
      wc = <DriveInfo sn={this.props.sn} />;
    }

    if ( this.props.content === "driveInfo2" ){
      wc = <DriveInfo2 sn={this.props.sn} />;
    }

    return (
      <div className={"widget " + this.props.size} style={divStyle}>
        <header>
          <span className="widgetTitle">{this.props.title} <Icon glyph="gear" icoSize="lg" /></span>
        </header>
        <div className="widgetContent">
          { wc }
        </div>
      </div>
    );
  }
});

module.exports = Widget;