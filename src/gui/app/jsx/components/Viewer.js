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
    , displayData  : React.PropTypes.object
  }

  , getDefaultProps: function() {
      // Viewer allows all modes by default, except for heirarchical. This list
      // can be overwritten by passing allowedModes into your <Viewer />.
      // Allowed modes are:
      // "detail" : Items on left, with properties on right, cnofigurable
      // "icon"   : Items as icons, with properties as modal
      // "table"  : Items as table rows, showing more data
      // TODO: "heir"   : Heirarchical view, shows relationships between items
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
          currentMode    : this.changeViewMode( initialMode )
        , tableCols      : defaultTableCols
        , enabledGroups  : this.props.displayData.defaultGroups.length ? this.props.displayData.defaultGroups : null
        , enabledFilters : this.props.displayData.defaultFilters.length ? this.props.displayData.defaultFilters : null
        , filteredData   : {
              grouped   : false
            , groups    : []
            , remaining : {
                entries: []
              }
          }
        , searchString   : ""
      };
    }

  , componentWillReceiveProps: function ( nextProps ) {
      this.processDisplayData( nextProps.inputData, this.state.searchString );
    }

  , processDisplayData: function ( inputData, searchString ) {
      // This function applys filters, searches, and then groups before handing
      // the data to any of its sub-views. The structure is deliberately generic
      // so that any sub-view may display the resulting data as it sees fit

      // Prevent function from modifying nextProps
      var inputDataArray = _.cloneDeep( inputData );
      var filteredData = {
          grouped   : false
        , groups    : []
        , remaining : {}
      };

      // Reduce the array by applying exclusion filters (defined in the view)
      // TODO: Debug this - doesn't work right!
      if ( this.state.enabledFilters ) {
        this.state.enabledFilters.map(
          function ( filter ) {
            inputDataArray = _.remove( inputDataArray, this.props.displayData.filterCriteria[ filter ].testProp );
          }.bind(this)
        );
      }

      // Reduce the array to only items which contain a substring match for the
      // searchString in either their primary or secondary keys
      inputDataArray = _.filter( inputDataArray, function ( item ) {
        // TODO: Are keys always strings? May want to rethink this
        var searchableString = item[ this.props.formatData.primaryKey ] + item[ this.props.formatData.secondaryKey ];

        return ( searchableString.indexOf( searchString ) !== -1 );

      }.bind(this) );

      // Convert array into object based on groups
      if ( this.state.enabledGroups ) {
        this.state.enabledGroups.map(
          function ( group ) {
            var groupData  = this.props.displayData.filterCriteria[ group ];
            var newEntries = _.remove( inputDataArray, groupData.testProp );

            filteredData.groups.push({
                name    : groupData.name
              , entries : newEntries
            });
          }.bind(this)
        );

        filteredData["grouped"] = true;
      } else {
        filteredData["grouped"] = false;
      }

      // All remaining items are put in the "remaining" property
      filteredData["remaining"] = {
          name    : ""
        , entries : inputDataArray
      };

      this.setState({
          filteredData : filteredData
        , searchString : searchString
      });
    }

  , handleSearchChange: function ( event ) {
      this.processDisplayData( this.props.inputData, event.target.value );
  }

  , changeViewMode: function ( targetMode ) {
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

  , changeTargetItem: function( params ) {
      return _.find( this.props.inputData, function( item ) {
          // Returns the first object from the input array whose selectionKey matches
          // the current route's dynamic portion. For instance, /accounts/users/root
          // with bsdusr_usrname as the selectionKey would match the first object
          // in inputData whose username === "root"
          return params[ this.props.itemData["param"] ] === item[ this.props.formatData["selectionKey"] ];
        }.bind(this)
      );
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
          return( <DetailViewer filteredData = { this.state.filteredData }
                                searchString = { this.state.searchString }
                                inputData    = { this.props.inputData }
                                formatData  = { this.props.formatData }
                                itemData    = { this.props.itemData }
                                ItemView    = { this.props.ItemView }
                                Editor      = { this.props.Editor } /> );
        case "icon":
          return( <IconViewer inputData  = { this.props.inputData }
                                searchString = { this.state.searchString }
                              formatData = { this.props.formatData }
                              ItemView   = { this.props.ItemView }
                              Editor     = { this.props.Editor } /> );
        case "table":
          return( <TableViewer inputData  = { this.props.inputData }
                                searchString = { this.state.searchString }
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
          <TWBS.Input type           = "text"
                      placeholder    = "Search"
                      value          = { this.state.searchString }
                      groupClassName = "navbar-form navbar-left"
                      onChange       = { this.handleSearchChange }
                      addonBefore    = { <Icon glyph ="search" /> } />
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