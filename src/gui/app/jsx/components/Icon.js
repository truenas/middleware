/** @jsx React.DOM */

"use strict";

var React = require("react");

var Icon = React.createClass({
  render: function() {
    var sizeString = null;
    if (this.props.sizee !== undefined)
    {
    	sizeString = " fa-" + this.props.sizee;
    } 

    return (
      <i className={ "fa fa-" + this.props.glyph + sizeString}></i>
    );
  }
});

module.exports = Icon;