"use strict";

var React = require("react");
var _     = require("lodash");
var TWBS  = require("react-bootstrap");

var viewerCommon = require("./mixins/viewerCommon");

var Icon         = require("./Icon");
var DetailViewer = require("./Viewer/DetailViewer");
var IconViewer   = require("./Viewer/IconViewer");
var TableViewer  = require("./Viewer/TableViewer");


// Main Viewer Wrapper Component
var Viewer = React.createClass({

    mixins: [ viewerCommon ]

  , contextTypes: {
      router: React.PropTypes.func
    }

  , propTypes: {
        defaultMode  : React.PropTypes.string
      , allowedModes : React.PropTypes.array
      , inputData    : React.PropTypes.array.isRequired
      , addEntity    : React.PropTypes.string
      , viewData     : React.PropTypes.object.isRequired
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

      _.filter( this.props.viewData.format.dataKeys, function( item, key, collection ) {
        if ( item["defaultCol"] ) {
          defaultTableCols.push( item["key"] );
        }
      });

      return {
          currentMode    : this.changeViewerMode( initialMode )
        , tableCols      : defaultTableCols
        , enabledGroups  : this.props.viewData.display.defaultGroups.length ? this.props.viewData.display.defaultGroups : null
        , enabledFilters : this.props.viewData.display.defaultFilters.length ? this.props.viewData.display.defaultFilters : null
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
        , rawList   : []
      };


      // Reduce the array by applying exclusion filters (defined in the view)
      // TODO: Debug this - doesn't work right!
      if ( displayParams.enabledFilters ) {
        displayParams.enabledFilters.map(
          function ( filter ) {
            _.remove( inputDataArray, this.props.viewData.display.filterCriteria[ filter ].testProp );
          }.bind(this)
        );
      }


      // Reduce the array to only items which contain a substring match for the
      // searchString in either their primary or secondary keys
      inputDataArray = _.filter( inputDataArray, function ( item ) {
        // TODO: Are keys always strings? May want to rethink this
        var searchableString = item[ this.props.viewData.format.primaryKey ] + item[ this.props.viewData.format.secondaryKey ] || "";
        searchableString = searchableString.toLowerCase();

        return ( searchableString.indexOf( displayParams.searchString.toLowerCase() ) !== -1 );

      }.bind(this) );

      // At this point, inputDataArray is an ungrouped (but filtered) list of
      // items, useful for views like the table.
      filteredData["rawList"] = _.clone( inputDataArray );


      // Convert array into object based on groups
      if ( displayParams.enabledGroups.length ) {
        displayParams.enabledGroups.map(
          function ( group ) {
            var groupData  = this.props.viewData.display.filterCriteria[ group ];
            var newEntries = _.remove( inputDataArray, groupData.testProp );

            filteredData.groups.push({
                name    : groupData.name
              , key     : group
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
          name    : filteredData["grouped"] ? this.props.viewData.display["remainingName"] : this.props.viewData.display["ungroupedName"]
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
      var tempDisplayArray = this.props.viewData.display.allowedGroups;
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

      // When changing viewer modes, close any previously open items.
      // TODO: This may need to change with single-click select functionality.
      this.returnToViewerRoot();

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
          return params[ this.props.viewData.routing["param"] ] === item[ this.props.viewData.format["selectionKey"] ];
        }.bind(this)
      );
    }


  // VIEWER DISPLAY
  , createModeNav: function ( mode, index ) {
      var modeIcons = {
          "detail" : "th-list"
        , "icon"   : "th"
        , "table"  : "align-justify"
        , "heir"   : "bell"
      };

      return (
        <TWBS.Button onClick = { function() { this.handleModeSelect( mode ); }.bind(this) }
                     key     = { index }
                     bsStyle = { ( mode === this.state.currentMode ) ? "info" : "default" }
                     active  = { false } >
          <Icon glyph = { modeIcons[ mode ] } />
        </TWBS.Button>
      );
    }

  , createViewerContent: function () {
      var ViewerContent = null;

      switch ( this.state.currentMode ) {
        default:
        case "detail":
          ViewerContent = DetailViewer;
          break;

        case "icon":
          ViewerContent = IconViewer;
          break;

        case "table":
          ViewerContent = TableViewer;
          break;

        case "heir":
          // TODO: Heirarchical Viewer
          break;
      }

      return <ViewerContent viewData     = { this.props.viewData }
                            inputData    = { this.props.inputData }
                            Editor       = { this.props.Editor }
                            ItemView     = { this.props.ItemView }
                            EditView     = { this.props.EditView }
                            addEntity    = { this.props.addEntity}
                            tableCols    = { this.state.tableCols }
                            searchString = { this.state.searchString }
                            filteredData = { this.state.filteredData } />;
    }

  , render: function() {
      var viewerModeNav = null;

      // Create navigation mode icons
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

            {/* Select view mode (3) */}
            { viewerModeNav }

          </TWBS.Navbar>

          { this.createViewerContent() }
        </div>
      );
    }

});

module.exports = Viewer;
