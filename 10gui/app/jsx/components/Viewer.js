/** @jsx React.DOM */

"use strict";

var React = require("react");

// Twitter Bootstrap React components
var TWBS = require("react-bootstrap");


// Detail Viewer
var DetailViewer = React.createClass({
  render: function() {
    var createItem = function( rawItem ) {
      return ( <TWBS.ListGroupItem header = { rawItem[ this.props.displayData.primary ] }
                                   key    = { rawItem.id }>
                 { rawItem[ this.props.displayData.secondary ] }
               </TWBS.ListGroupItem> );
    }.bind(this);
    return (
      <TWBS.Row>
        <TWBS.Col xs={4}>
          <TWBS.ListGroup>
            { this.props.displayData.inputData.map( createItem ) }
          </TWBS.ListGroup>
        </TWBS.Col>
        <TWBS.Col xs={8}>
          <p>{"TODO: Data for the selected item should display here"}</p>
        </TWBS.Col>
      </TWBS.Row>
    );
  }
});

// Icon Viewer
var IconViewer = React.createClass({
  render: function() {
    var createItem = function( rawItem ) {
      return (
        <TWBS.Col xs  = {2}
                  key = { rawItem.id } >
          <h6>{ rawItem[ this.props.displayData.primary ] }</h6>
          <small className="text-muted">{ rawItem[ this.props.displayData.secondary ] }</small>
        </TWBS.Col>
      );
    }.bind(this);
    return (
      <TWBS.Row>
        { this.props.displayData.inputData.map( createItem ) }
      </TWBS.Row>
    );
  }
});

// Main Viewer Component
var Viewer = React.createClass({
    changeViewMode: function( targetMode ) {
      var newMode;

      // See if a disallowed mode has been requested
      if ( this.props.allowedModes.indexOf( targetMode ) === -1 ) {
        console.log( "Error: Attempted to set mode " + targetMode + " in a Viewer which forbids it");
        if ( this.props.defaultMode ) {
          // Use the default mode, if provided
          console.log( "Note: Substituted provided default, " + this.props.defaultMode + " instead of " + targetMode );
          newMode = this.props.defaultMode;
        } else {
          // If no default, use the first allowed mode in the list
          newMode = this.props.allowedModes[0];
        }
      } else {
        newMode = targetMode;
      }

      return newMode;
   }
   , handleModeSelect: function( selectedKey ) {
      this.setState({
        currentMode: this.changeViewMode( this.props.allowedModes[ selectedKey ] )
      });
   }
   , propTypes: {
        defaultMode  : React.PropTypes.string
      , allowedModes : React.PropTypes.array
      , displayData  : React.PropTypes.object.isRequired
    }
  , getDefaultProps: function() {
      // Viewer allows all modes by default, except for heirarchical. This list
      // can be overwritten by passing allowedModes into your <Viewer />.
      // Allowed modes are:
      // "detail" : Items on left, with properties on right, cnofigurable
      // "icon"   : Items as icons, with properties as modal
      // "table"  : Items as table rows, showing more data
      // "heir"   : Heirarchical view, shows relationships between items
      return {
        allowedModes: [ "detail", "icon", "table" ]
      };
    }
  , getInitialState: function() {
      // render will always use currentMode - in an uninitialized Viewer, the
      // mode will not have been set, and should therefore come from either a
      // passed in currentMode or defaultMode, falling back to getDefaultProps
      var initialMode = ( this.props.currentMode || this.props.defaultMode || "detail" );

      return {
        currentMode: this.changeViewMode( initialMode )
      };
    }
  , render: function() {
    // Navigation
    var createModeNav = function( mode ) {
      return ( <TWBS.NavItem key = { this.props.allowedModes.indexOf( mode ) }>
                 { mode }
               </TWBS.NavItem> );
    }.bind(this);

    // Select view based on current mode
    var viewerContent = function() {
      switch ( this.state.currentMode ) {
        default:
        case "detail":
          return( <DetailViewer displayData={ this.props.displayData } /> );
        case "icon":
          return( <IconViewer displayData={ this.props.displayData } /> );
        case "table":
          // TODO: Table Viewer
          break;
        case "heir":
          // TODO: Heirarchical Viewer
          break;
      }
    }.bind(this);

    return (
      <TWBS.Panel header={ this.props.header }>
        <TWBS.Nav bsStyle="pills"
                  justified
                  onSelect  = { this.handleModeSelect }
                  activeKey = { this.props.allowedModes.indexOf( this.state.currentMode ) } >
          { this.props.allowedModes.map( createModeNav ) }
        </TWBS.Nav>
        { viewerContent() }
      </TWBS.Panel>
    );
  }
});

module.exports = Viewer;