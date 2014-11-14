/** @jsx React.DOM */

"use strict";

var React = require("react");

var Router = require("react-router");
var Link   = Router.Link;

var Icon   = require("./Icon");
var TWBS   = require("react-bootstrap");

var WarningBox = React.createClass({
    getDefaultProps: function() {
    return {
      isVisible: 0
    };
  },
  render: function() {    
    return (            
      <div className={"notifyBoxes warningBox "  + ((this.props.isVisible) ? "visible" : "hidden") }>
        <div className="item">     
          <h3><Icon glyph="warning" icoSize="1x" /> Reading Error at position 542 on pool <strong>HONK1</strong></h3>
          <div className="status">
            {"Error code #1234 Details about this error"}
          </div>
        </div>
        <div className="item">
          <h3><Icon glyph="warning" icoSize="1x" /> Reading Error at position 432 on pool <strong>HONK1</strong></h3>
          <div className="status">
            {"Error code #1234 Details about this error"}
          </div>
        </div>
      </div>
    );
  }
});

module.exports = WarningBox;