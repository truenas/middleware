/** @jsx React.DOM */

"use strict";

var React = require("react");

var Icon = React.createClass({
  render: function() {
    var sizeString  = "";
    var classString = "";
    var flagElement = null;

    if ( this.props.icoSize ) {
      sizeString = " fa-" + this.props.icoSize;
    }
    if ( this.props.icoClass ) {
      classString = " " + this.props.icoClass;
    }
    if ( this.props.warningFlag ) {
      flagElement = <span> { this.props.warningFlag } </span>;
    }

    return (
      <i onClick   = { this.props.onClick }
         className = { "fa fa-" + this.props.glyph + sizeString + classString }>{ flagElement }</i>
    );
  }
});

module.exports = Icon;