/** @jsx React.DOM */

"use strict";

var React = require("react");
var _     = require("lodash");
var TWBS  = require("react-bootstrap");

var Icon   = require("./Icon");

var DetailViewer = require("./Viewer/DetailViewer");
var IconViewer   = require("./Viewer/IconViewer");
var TableViewer  = require("./Viewer/TableViewer");


// Main Viewer Wrapper Component
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
        currentMode: this.changeViewMode( selectedKey )
      });
   }
   , handleItemSelect: function( selectedKey ) {
      this.setState({ selectedItem: selectedKey });
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
          currentMode  : this.changeViewMode( initialMode )
        , tableCols    : defaultTableCols
        , selectedItem : this.props.inputData[0][ this.props.formatData.selectionKey ]
      };
    }
  , render: function() {
    // Navigation
    var modeIcons = {
        "detail" : "th-list"
      , "icon"   : "th"
      , "table"  : "align-justify"
      , "heir"   : "bell"
    };

    var createModeNav = function( mode ) {
      var changeMode = function() {
        this.handleModeSelect( mode );
      }.bind(this);

      return (
        <TWBS.Button onClick = { changeMode }
                     key     = { this.props.allowedModes.indexOf( mode ) }
                     bsStyle = { ( mode === this.state.currentMode ) ? "primary" : "default" }>
          <Icon glyph = { modeIcons[ mode ] } />
        </TWBS.Button>
      );
    }.bind(this);

    // Select view based on current mode
    var viewerContent = function() {
      switch ( this.state.currentMode ) {
        default:
        case "detail":
          return( <DetailViewer inputData        = { this.props.inputData }
                                formatData       = { this.props.formatData }
                                handleItemSelect = { this.handleItemSelect }
                                selectedKey      = { this.state.selectedItem } /> );
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
        <TWBS.ButtonGroup activeMode={ this.state.currentMode } >
          { this.props.allowedModes.map( createModeNav ) }
        </TWBS.ButtonGroup>
        { viewerContent() }
      </TWBS.Panel>
    );
  }
});

module.exports = Viewer;