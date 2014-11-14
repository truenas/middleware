/** @jsx React.DOM */

"use strict";

var React = require("react");

var Router = require("react-router");
var Link   = Router.Link;

var Icon   = require("./Icon");
var TWBS   = require("react-bootstrap");

var InfoBox = React.createClass({
  getDefaultProps: function() {
    return {
      isVisible: 0
    };
  },
  render: function() {
  	//console.log(this.props.isVisible);
    return (
      <div className={"notifyBoxes infoBox "  + ((this.props.isVisible) ? "visible" : "hidden") }>
       	<div className="item">     
		    <h3>User <strong>Jakub Klama</strong> logged in as <strong>administrator</strong></h3>
		    <div className="status">
		     	{"Nov 14 11:20am"}
		    </div>
	    </div>
	    <div className="item">
		     <h3>User <strong>Kevin Bacon</strong> created dataset <strong>KEVIN</strong></h3>
		     <div className="status">
		     	{"Nov 14 11:10am"}
			</div>
	    </div>
      </div>
    );
  }
});

module.exports = InfoBox;	