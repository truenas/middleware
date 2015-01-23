/** @jsx React.DOM */

// Throbber
// ========

"use strict";

var React = require("react");

var Throbber = React.createClass({

  render: function() {
    return (
      <div className={ "throbber" + ( this.props.bsStyle ? " throbber-" + this.props.bsStyle : "" ) } />
    );
  }

});

module.exports = Throbber;
