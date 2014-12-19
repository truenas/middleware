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


  // REACT LIFECYCLE

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
          currentMode    : this.changeViewerMode( initialMode )
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
      this.processDisplayData({ inputData: nextProps.inputData });
    }


  // VIEWER DATA HANDLING

    // processDisplayData applys filters, searches, and then groups before handing
    // the data to any of its sub-views. The structure is deliberately generic
    // so that any sub-view may display the resulting data as it sees fit.
  , processDisplayData: function ( options ) {
      var displayParams = {
          inputData      : this.props.inputData
        , searchString   : this.state.searchString
        , enabledGroups  : this.state.enabledGroups
        , enabledFilters : this.state.enabledFilters
      };

      _.assign( displayParams, options );

      // Prevent function from modifying nextProps
      var inputDataArray = _.cloneDeep( displayParams.inputData );
      var filteredData = {
          grouped   : false
        , groups    : []
        , remaining : {}
      };


      // Reduce the array by applying exclusion filters (defined in the view)
      // TODO: Debug this - doesn't work right!
      if ( displayParams.enabledFilters ) {
        displayParams.enabledFilters.map(
          function ( filter ) {
            _.remove( inputDataArray, this.props.displayData.filterCriteria[ filter ].testProp );
          }.bind(this)
        );
      }


      // Reduce the array to only items which contain a substring match for the
      // searchString in either their primary or secondary keys
      inputDataArray = _.filter( inputDataArray, function ( item ) {
        // TODO: Are keys always strings? May want to rethink this
        var searchableString = item[ this.props.formatData.primaryKey ] + item[ this.props.formatData.secondaryKey ];

        return ( searchableString.indexOf( displayParams.searchString ) !== -1 );

      }.bind(this) );


      // Convert array into object based on groups
      if ( displayParams.enabledGroups.length ) {
        displayParams.enabledGroups.map(
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
          name    : filteredData["grouped"] ? this.props.displayData["remainingName"] : this.props.displayData["ungroupedName"]
        , entries : inputDataArray
      };

      this.setState({
          filteredData   : filteredData
        , searchString   : displayParams.searchString
        , enabledGroups  : displayParams.enabledGroups
        , enabledFilters : displayParams.enabledFilters
      });
    }

  , handleSearchChange: function ( event ) {
      this.processDisplayData({ searchString: event.target.value });
    }

  , handleEnabledGroupsToggle: function ( targetGroup ) {
      var tempEnabledArray = _.clone( this.state.enabledGroups );
      var tempDisplayArray = this.props.displayData.allowedGroups;
      var enabledIndex     = tempEnabledArray.indexOf( targetGroup );

      if ( enabledIndex !== -1 ) {
        tempEnabledArray.splice( enabledIndex, 1 );
      } else {
        tempEnabledArray.push( targetGroup );
        // _.intersection will return array to the original defined order
        tempEnabledArray = _.intersection( tempDisplayArray, tempEnabledArray );
      }

      this.processDisplayData({ enabledGroups: tempEnabledArray });
    }

  , handleEnabledFiltersToggle: function ( targetFilter ) {
      var tempEnabledArray = _.clone( this.state.enabledFilters );
      var enabledIndex     = tempEnabledArray.indexOf( targetFilter );

      if ( enabledIndex !== -1 ) {
        tempEnabledArray.splice( enabledIndex, 1 );
      } else {
        tempEnabledArray.push( targetFilter );
      }

      this.processDisplayData({ enabledFilters: tempEnabledArray });
    }

  , changeViewerMode: function ( targetMode ) {
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
     this.setState({ currentMode: this.changeViewerMode( selectedKey ) });
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


  // VIEWER DISPLAY

  , createGroupMenuOption: function ( group, index ) {
      var toggleText;

      if ( this.state.enabledGroups.indexOf( group ) !== -1 ) {
        toggleText = "Don't group ";
      } else {
        toggleText = "Group ";
      }

      return (
        <TWBS.MenuItem key        = { index }
                       onClick    = { this.handleEnabledGroupsToggle.bind( null, group ) }>
          { toggleText + this.props.displayData.filterCriteria[ group ].name }
        </TWBS.MenuItem>
      );
    }

  , createFilterMenuOption: function ( filter, index ) {
      var toggleText;

      if ( this.state.enabledFilters.indexOf( filter ) !== -1 ) {
        toggleText = "Show ";
      } else {
        toggleText = "Hide ";
      }

      return (
        <TWBS.MenuItem key        = { index }
                       onClick    = { this.handleEnabledFiltersToggle.bind( null, filter ) }>
          { toggleText + this.props.displayData.filterCriteria[ filter ].name }
        </TWBS.MenuItem>
      );
    }

  , createModeNav: function ( mode ) {
      var modeIcons = {
          "detail" : "th-list"
        , "icon"   : "th"
        , "table"  : "align-justify"
        , "heir"   : "bell"
      };

      return (
        <TWBS.Button onClick = { function() { this.handleModeSelect( mode ); }.bind(this) }
                     key     = { this.props.allowedModes.indexOf( mode ) }
                     bsStyle = { ( mode === this.state.currentMode ) ? "info" : "default" }
                     active  = { false } >
          <Icon glyph = { modeIcons[ mode ] } />
        </TWBS.Button>
      );
    }

  , createViewerContent: function () {
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
    }

  , render: function() {
      var groupDropdown  = null;
      var filterDropdown = null;
      var viewerModeNav  = null;

      if ( this.props.displayData.allowedGroups ) {
        // Don't show grouping toggle for hidden groups
        var visibleGroups = _.difference( this.props.displayData.allowedGroups, this.state.enabledFilters );

        groupDropdown = (
          <TWBS.DropdownButton title="Group">
            { visibleGroups.map( this.createGroupMenuOption ) }
          </TWBS.DropdownButton>
        );
      }

      if ( this.props.displayData.allowedFilters ) {
        filterDropdown = (
          <TWBS.DropdownButton title="Filter">
            { this.props.displayData.allowedFilters.map( this.createFilterMenuOption ) }
          </TWBS.DropdownButton>
        );
      }

      if ( this.props.allowedModes.length > 1 ) {
        viewerModeNav = (
          <TWBS.ButtonGroup className="navbar-btn navbar-right" activeMode={ this.state.currentMode } >
            { this.props.allowedModes.map( this.createModeNav ) }
          </TWBS.ButtonGroup>
        );
      }

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
              { groupDropdown }

              {/* Select properties to filter by */}
              { filterDropdown }

              {/* Select property to sort by */}
              {/* <TWBS.DropdownButton title="Sort">
                <TWBS.MenuItem key="1">Action</TWBS.MenuItem>
                <TWBS.MenuItem key="2">Another action</TWBS.MenuItem>
                <TWBS.MenuItem key="3">Something else here</TWBS.MenuItem>
                <TWBS.MenuItem divider />
                <TWBS.MenuItem key="4">Separated link</TWBS.MenuItem>
              </TWBS.DropdownButton> */}
            </TWBS.Nav>

            {/* Select view mode (3) */}
            { viewerModeNav }

          </TWBS.Navbar>

          { this.createViewerContent() }
        </div>
      );
    }

});

module.exports = Viewer;