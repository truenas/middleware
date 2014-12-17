/** @jsx React.DOM */

"use strict";

var React = require("react");
var _     = require("lodash");
var TWBS  = require("react-bootstrap");

var Icon         = require("./Icon");
var DetailViewer = require("./Viewer/DetailViewer");
var IconViewer   = require("./Viewer/IconViewer");
var TableViewer  = require("./Viewer/TableViewer");


// Main Viewer Wrapper Component
var Viewer = React.createClass({

    propTypes: {
      defaultMode  : React.PropTypes.string
    , allowedModes : React.PropTypes.array
    , itemData     : React.PropTypes.object.isRequired
    , inputData    : React.PropTypes.array.isRequired
    , formatData   : React.PropTypes.object.isRequired
  }

  , changeViewMode: function( targetMode ) {
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
          defaultTableCols.push( item["key"] );
        }
      });

      return {
          currentMode  : this.changeViewMode( initialMode )
        , tableCols    : defaultTableCols
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
                     bsStyle = { ( mode === this.state.currentMode ) ? "info" : "default" }
                     active  = { false } >
          <Icon glyph = { modeIcons[ mode ] } />
        </TWBS.Button>
      );
    }.bind(this);

    // Select view based on current mode
    var viewerContent = function() {
      switch ( this.state.currentMode ) {
        default:
        case "detail":
          return( <DetailViewer inputData  = { this.props.inputData }
                                formatData = { this.props.formatData }
                                itemData   = { this.props.itemData }
                                ItemView   = { this.props.ItemView }
                                Editor     = { this.props.Editor } /> );
        case "icon":
          return( <IconViewer inputData  = { this.props.inputData }
                              formatData = { this.props.formatData }
                              ItemView   = { this.props.ItemView }
                              Editor     = { this.props.Editor } /> );
        case "table":
          return( <TableViewer inputData  = { this.props.inputData }
                               formatData = { this.props.formatData }
                               tableCols  = { this.state.tableCols }
                               ItemView   = { this.props.ItemView }
                               Editor     = { this.props.Editor } /> );
        case "heir":
          // TODO: Heirarchical Viewer
          break;
      }
    }.bind(this);

    return (
      <div className="viewer">
        <TWBS.Navbar fluid className="viewer-nav">
          {/* Searchbox for Viewer (1) */}
          <TWBS.Input type="text"
                      placeholder="Search"
                      groupClassName="navbar-form navbar-left"
                      addonBefore={ <Icon glyph ="search" /> } />
          {/* Dropdown buttons (2) */}
          <TWBS.Nav className="navbar-left">
            {/* Select properties to group by */}
            <TWBS.DropdownButton title="Group">
              <TWBS.MenuItem key="1">Action</TWBS.MenuItem>
              <TWBS.MenuItem key="2">Another action</TWBS.MenuItem>
              <TWBS.MenuItem key="3">Something else here</TWBS.MenuItem>
              <TWBS.MenuItem divider />
              <TWBS.MenuItem key="4">Separated link</TWBS.MenuItem>
            </TWBS.DropdownButton>
            {/* Select properties to filter by */}
            <TWBS.DropdownButton title="Filter">
              <TWBS.MenuItem key="1">Action</TWBS.MenuItem>
              <TWBS.MenuItem key="2">Another action</TWBS.MenuItem>
              <TWBS.MenuItem key="3">Something else here</TWBS.MenuItem>
              <TWBS.MenuItem divider />
              <TWBS.MenuItem key="4">Separated link</TWBS.MenuItem>
            </TWBS.DropdownButton>
            {/* Select property to sort by */}
            <TWBS.DropdownButton title="Sort">
              <TWBS.MenuItem key="1">Action</TWBS.MenuItem>
              <TWBS.MenuItem key="2">Another action</TWBS.MenuItem>
              <TWBS.MenuItem key="3">Something else here</TWBS.MenuItem>
              <TWBS.MenuItem divider />
              <TWBS.MenuItem key="4">Separated link</TWBS.MenuItem>
            </TWBS.DropdownButton>
          </TWBS.Nav>
          {/* Select view mode (3) */}
          <TWBS.ButtonGroup className="navbar-btn navbar-right" activeMode={ this.state.currentMode } >
            { this.props.allowedModes.map( createModeNav ) }
          </TWBS.ButtonGroup>
        </TWBS.Navbar>

        { viewerContent() }
      </div>
    );
  }

});

module.exports = Viewer;