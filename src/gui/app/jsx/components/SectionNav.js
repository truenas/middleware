/** @jsx React.DOM */

// Sections
// ================
// Component for managing multiple views side by side

"use strict";

var React = require("react");
var TWBS  = require("react-bootstrap");

var Router = require("react-router");
var Link   = Router.Link;

var Navigation = React.createClass({
    propTypes: {
      views : React.PropTypes.array.isRequired
    }
  , createNavItems: function( item, index ) {
      return (
        <Link to              = { item.route }
              key             = { index }
              className       = "btn btn-default"
              activeClassName = "active btn-info"
              role            = "button"
              type            = "button">{ item.display }</Link>
      );
    }
  , render: function() {
      return (
        <TWBS.Row className="text-center">
          <TWBS.ButtonGroup bsSize="large">
            { this.props.views.map( this.createNavItems ) }
          </TWBS.ButtonGroup>
        </TWBS.Row>
      );
    }
});

var Sections = React.createClass({
    propTypes: {
      views: React.PropTypes.array
    }
  , render: function() {
    if ( this.props.views.length > 1 ) {
      return (
        <TWBS.Grid fluid>
          <Navigation views={ this.props.views } />
        </TWBS.Grid>
      );
    } else {
      console.log("Warning: A SectionNav is being called with " + ( this.props.views.length === 1 ) ? "only one view" : "no views" );
      return null;
    }
  }
});

module.exports = Sections;
