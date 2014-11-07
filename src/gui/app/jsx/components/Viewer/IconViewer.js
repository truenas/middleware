/** @jsx React.DOM */

"use strict";

var React = require("react");
var _     = require("lodash");
var TWBS  = require("react-bootstrap");

// var Editor = require("./Editor");

// Icon Viewer
var IconViewer = React.createClass({
  render: function() {
    var createItem = function( rawItem ) {
      return (
        <TWBS.Col xs  = {2}
                  key = { rawItem.id } >
          <h6>{ rawItem[ this.props.formatData["primaryKey"] ] }</h6>
          <small className="text-muted">{ rawItem[ this.props.formatData["secondaryKey"] ] }</small>
        </TWBS.Col>
      );
    }.bind(this);

    return (
      <TWBS.Row>
        { this.props.inputData.map( createItem ) }
      </TWBS.Row>
    );
  }
});

module.exports = IconViewer;