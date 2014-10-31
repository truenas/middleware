/** @jsx React.DOM */

"use strict";

var React = require("react");

var _ = require("lodash");

// Twitter Bootstrap React components
var TWBS = require("react-bootstrap");


// Detail Viewer
var DetailViewer = React.createClass({
  render: function() {
    var createItem = function( rawItem ) {
      return ( <TWBS.ListGroupItem header = { rawItem[ this.props.formatData["primaryKey"] ] }
                                   key    = { rawItem.id }>
                 { rawItem[ this.props.formatData["secondaryKey"] ] }
               </TWBS.ListGroupItem> );
    }.bind(this);

    return (
      <TWBS.Row>
        <TWBS.Col xs={4}>
          <TWBS.ListGroup>
            { this.props.inputData.map( createItem ) }
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

// Table Viewer
var TableViewer = React.createClass({
  render: function() {
    var createHeader = function( key ) {
      return(
        <th key={ key.id } >
          { this.props.formatData.dataKeys[key]["name"] }
        </th>
      );
    }.bind(this);

    var createRows = function( rawItem ) {
      var createCell = function( cellKey ) {
        var innerContent;
        if ( typeof rawItem[cellKey] === "boolean" ) {
          innerContent = ( rawItem ? "Yes" : "No" );
        } else if ( rawItem[cellKey].length === 0 ) {
          innerContent = <span className="text-muted">{"--"}</span>;
        } else {
          innerContent = rawItem[cellKey];
        }
        return ( <td key={ cellKey.key }>{ innerContent }</td> );
      }.bind( this );

      return(
        <tr key={ rawItem.id } >
          { this.props.tableCols.map( createCell ) }
        </tr>
      );
    }.bind(this);

    return(
      <TWBS.Table striped bordered condensed hover responsive>
        <thead>
          <tr>
            { this.props.tableCols.map( createHeader ) }
          </tr>
        </thead>
        <tbody>
          { this.props.inputData.map( createRows ) }
        </tbody>
      </TWBS.Table>
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
      , inputData    : React.PropTypes.array.isRequired
      , formatData   : React.PropTypes.object.isRequired
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

      // Generate an array of keys which TableViewer can use to quickly generate
      // its internal structure by looping through the returned data from the
      // middleware and creating cells. Also useful for getting human-friendly
      // names out of the translation key.
      var defaultTableCols = [];

      _.filter( this.props.formatData.dataKeys, function( item, key, collection ) {
        if ( item["defaultCol"] ) {
          defaultTableCols.push( key );
        }
      });

      return {
          currentMode : this.changeViewMode( initialMode )
        , tableCols   : defaultTableCols
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
          return( <DetailViewer inputData  = { this.props.inputData }
                                formatData = { this.props.formatData } /> );
        case "icon":
          return( <IconViewer inputData  = { this.props.inputData }
                              formatData = { this.props.formatData } /> );
        case "table":
          return( <TableViewer inputData  = { this.props.inputData }
                               formatData = { this.props.formatData }
                               tableCols  = { this.state.tableCols } /> );
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