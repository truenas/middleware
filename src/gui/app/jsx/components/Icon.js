/** @jsx React.DOM */

"use strict";

var React = require("react");

var Icon = React.createClass({
  render: function() {
    return (
      <i className={ "fa fa-" + this.props.glyph }></i>
    );
  }
});

module.exports = Icon;