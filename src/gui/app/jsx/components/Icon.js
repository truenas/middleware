/** @jsx React.DOM */

"use strict";

var React = require("react");

var Icon = React.createClass({
  render: function() {
    var sizeString = "";
    if (this.props.icoSize !== undefined)
    {
    	sizeString = " fa-" + this.props.icoSize;
    } 

    return (
      <i className={ "fa fa-" + this.props.glyph + sizeString }></i>
    );
  }
});

module.exports = Icon;