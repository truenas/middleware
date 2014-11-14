/** @jsx React.DOM */

"use strict";

var React = require("react");

var Icon = React.createClass({
  render: function() {
    var sizeString = "";
    var classString = "";
    var flagString = "";
    if (this.props.icoSize !== undefined)
    {
    	sizeString = " fa-" + this.props.icoSize;
    } 
    if (this.props.icoClass !== undefined)
    {
    	classString = " " + this.props.icoClass;
    }
    if (this.props.warningFlag !== undefined)
    {
    	flagString = <span> { this.props.warningFlag } </span>;
    }


    
    return (
      <i onClick={this.props.onClick} className={ "fa fa-" + this.props.glyph + sizeString + classString }>{ flagString }</i>
    );
  }
});

module.exports = Icon;