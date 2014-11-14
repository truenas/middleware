/** @jsx React.DOM */

"use strict";

var React = require("react");

var Router = require("react-router");
var Link   = Router.Link;

var Icon   = require("./Icon");
var TWBS   = require("react-bootstrap");

var QueueBox = React.createClass({
  getDefaultProps: function() {
    return {
      isVisible: 0
    };
  },
  render: function() {
    return (      
     <div className={"notifyBoxes queueBox "  + ((this.props.isVisible) ? "visible" : "hidden") }>
     	<div className="item">     
		    <h3>Running <strong>SCRUB</strong> on pool <strong>HONK1</strong></h3>
		    <div className="status">
		     	<TWBS.ProgressBar striped bsStyle="success" now={60}  label="%(percent)s%"/>
		    </div>
	    </div>
	    <div className="item">
		     <h3>Waiting to run <strong>SCRUB</strong> on pool <strong>KEVIN</strong></h3>
		     <div className="status">
		     	{"Waiting for previuos task."}
			</div>
	    </div>
     </div>
    );
  }
});

module.exports = QueueBox;