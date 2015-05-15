// VIEWER
// ======
// One of the primary display components in FreeNAS. The Viewer is capable of
// ingesting data sets or collections of "like" things, and displaying them in
// a variety of modes. It is similar in this way to a desktop client's browser
// window, though not limited to just displaying files.

"use strict";

import React from "react";
import _ from "lodash";
import TWBS from "react-bootstrap";

import viewerCommon from "./mixins/viewerCommon";

import Icon from "./Icon";
import DetailViewer from "./Viewer/DetailViewer";
import IconViewer from "./Viewer/IconViewer";
import TableViewer from "./Viewer/TableViewer";


// Main Viewer Wrapper Component
const Viewer = React.createClass(

  { mixins: [ viewerCommon ]

  , contextTypes: { router: React.PropTypes.func }

  , propTypes:
      { defaultMode: React.PropTypes.string
      , allowedModes: React.PropTypes.array
      , inputData: React.PropTypes.array.isRequired
      , viewData: React.PropTypes.object.isRequired
      , displayData: React.PropTypes.object
      }


  // REACT LIFECYCLE
  , getDefaultProps: function () {
      // Viewer allows all modes by default, except for heirarchical. This list
      // can be overwritten by passing allowedModes into your <Viewer />.
      // Allowed modes are:
      // "detail" : Items on left, with properties on right, cnofigurable
      // "icon"   : Items as icons, with properties as modal
      // "table"  : Items as table rows, showing more data
      // TODO: "heir"   : Heirarchical view, shows relationships between items
      return { allowedModes: [ "detail", "icon", "table" ] };
    }

  , getInitialState: function () {
      const VIEWDATA = this.props.viewData;
      // render will always use currentMode - in an uninitialized Viewer, the
      // mode will not have been set, and should therefore come from either a
      // passed in currentMode or defaultMode, falling back to getDefaultProps
      const INITIALMODE = ( this.props.currentMode ||
                            this.props.defaultMode ||
                            "detail"
                          );

      // Generate an array of keys which TableViewer can use to quickly generate
      // its internal structure by looping through the returned data from the
      // middleware and creating cells. Also useful for getting human-friendly
      // names out of the translation key.
      let defaultTableCols = [];
      let currentParams = this.context.router.getCurrentParams();
      let selectedItem = currentParams[ VIEWDATA.routing["param"] ];

      _.filter( VIEWDATA.format.dataKeys
              , function ( item, key, collection ) {
                  if ( item["defaultCol"] ) {
                    defaultTableCols.push( item["key"] );
                  }
                }
              );

      if ( !_.isNumber( selectedItem ) && !_.isString( selectedItem ) ) {
        selectedItem = null;
      }

      return (
        { currentMode: this.changeViewerMode( INITIALMODE )
        , tableCols: defaultTableCols
        , enabledGroups: VIEWDATA.display.defaultGroups.length
                       ? VIEWDATA.display.defaultGroups
                       : null
        , enabledFilters: VIEWDATA.display.defaultFilters.length
                        ? VIEWDATA.display.defaultFilters
                        : null
        , filteredData: { grouped: false
                        , groups: []
                        , remaining: { entries: [] }
                        }
        , searchString: ""
        , selectedItem: selectedItem
        }
      );
    }

  , componentWillReceiveProps: function ( nextProps ) {
      this.processDisplayData({ inputData: nextProps.inputData });
    }


  // VIEWER DATA HANDLING

    // processDisplayData applys filters, searches, and then groups before
    // handing the data to any of its sub-views. The structure is deliberately
    // generic so that any sub-view may display the resulting data as it
    // sees fit.
  , processDisplayData: function ( options ) {
      const VIEWDATA = this.props.viewData;

      let displayParams =
        { inputData: this.props.inputData
        , searchString: this.state.searchString
        , enabledGroups: this.state.enabledGroups
        , enabledFilters: this.state.enabledFilters
        };

      _.assign( displayParams, options );

      // Prevent function from modifying nextProps
      let inputDataArray = _.cloneDeep( displayParams.inputData );
      let filteredData = { grouped: false
                         , groups: []
                         , remaining: {}
                         , rawList: []
                         };


      // Reduce the array by applying exclusion filters (defined in the view)
      // TODO: Debug this - doesn't work right!
      if ( displayParams.enabledFilters ) {
        displayParams.enabledFilters.map(
          function ( filter ) {
            _.remove( inputDataArray
                    , VIEWDATA.display.filterCriteria[ filter ].testProp
                    );
          }.bind( this )
        );
      }


      // Reduce the array to only items which contain a substring match for the
      // searchString in either their primary or secondary keys
      inputDataArray =
        _.filter( inputDataArray
                , function ( item ) {
                    // TODO: Are keys always strings? May want to rethink this
                    let searchString = displayParams.searchString.toLowerCase();

                    let searchTarget = item[ VIEWDATA.format.primaryKey ] +
                                       item[ VIEWDATA.format.secondaryKey ] ||
                                       "";

                    return (
                      _.includes( searchTarget.toLowerCase()
                                , searchString
                                )
                    );
                  }
                );

      // At this point, inputDataArray is an ungrouped (but filtered) list of
      // items, useful for views like the table.
      filteredData["rawList"] = _.clone( inputDataArray );


      // Convert array into object based on groups
      if ( displayParams.enabledGroups.length ) {
        displayParams.enabledGroups.map(
          function ( group ) {
            let groupData  = VIEWDATA.display.filterCriteria[ group ];
            let newEntries = _.remove( inputDataArray, groupData.testProp );

            filteredData.groups.push(
              { name: groupData.name
              , key: group
              , entries: newEntries
              }
            );
          }
        );

        filteredData["grouped"] = true;
      } else {
        filteredData["grouped"] = false;
      }


      // All remaining items are put in the "remaining" property
      filteredData["remaining"] =
        { name: filteredData["grouped"]
              ? VIEWDATA.display["remainingName"]
              : VIEWDATA.display["ungroupedName"]
        , entries: inputDataArray
        };

      this.setState(
        { filteredData: filteredData
        , searchString: displayParams.searchString
        , enabledGroups: displayParams.enabledGroups
        , enabledFilters: displayParams.enabledFilters
        }
      );
    }

  , handleItemSelect: function ( selectionValue, event ) {
      let newSelection = null;

      if ( !_.isNumber( selectionValue ) || !_.isString( selectionValue ) ) {
        newSelection = selectionValue;
      }

      this.setState({ selectedItem: newSelection });
    }

  , handleSearchChange: function ( event ) {
      this.processDisplayData({ searchString: event.target.value });
    }

  , changeViewerMode: function ( targetMode ) {
      let newMode;

      // See if a disallowed mode has been requested
      if ( _.includes( this.props.allowedModes, targetMode ) ) {
        newMode = targetMode;
      } else {
        if ( this.props.defaultMode ) {
          // Use the default mode, if provided
          newMode = this.props.defaultMode;
        } else {
          // If no default, use the first allowed mode in the list
          newMode = this.props.allowedModes[0];
        }
      }

      // When changing viewer modes, close any previously open items.
      // TODO: This may need to change with single-click select functionality.
      this.returnToViewerRoot();

      return newMode;
    }

  , handleModeSelect: function ( selectedKey, foo, bar ) {
      this.setState({ currentMode: this.changeViewerMode( selectedKey ) });
    }

  , changeTargetItem: function ( params ) {
      // Returns the first object from the input array whose selectionKey
      // matches the current route's dynamic portion. For instance,
      // "/accounts/users/root" with "bsdusr_usrname" as the selectionKey would
      // match the first object in inputData whose username === "root"
      return _.find( this.props.inputData
                   , function ( item ) {
                       return (
                         params[ this.props.viewData.routing["param"] ] ===
                         item[ this.props.viewData.format["selectionKey"] ]
                       );
                     }.bind( this )
                   );
    }


  // VIEWER DISPLAY
  , createModeNav: function ( mode, index ) {
      var modeIcons = { detail: "th-list"
                      , icon: "th"
                      , table: "align-justify"
                      , heir: "bell"
                      };

      return (
        <TWBS.Button
          onClick = { this.handleModeSelect.bind( this, mode ) }
          key = { index }
          bsStyle = { ( mode === this.state.currentMode )
                    ? "info"
                    : "default"
                    }
          active = { false } >
          <Icon glyph = { modeIcons[ mode ] } />
        </TWBS.Button>
      );
    }

  , createViewerContent: function () {
      let ViewerContent = null;

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

      return <ViewerContent
                viewData = { this.props.viewData }
                inputData = { this.props.inputData }
                tableCols = { this.state.tableCols }
                handleItemSelect = { this.handleItemSelect }
                selectedItem = { this.state.selectedItem }
                searchString = { this.state.searchString }
                filteredData = { this.state.filteredData } />;
    }

  , render: function () {
      var viewerModeNav = null;

      // Create navigation mode icons
      if ( this.props.allowedModes.length > 1 ) {
        viewerModeNav = (
          <TWBS.ButtonGroup
            className = "navbar-btn navbar-right"
            activeMode = { this.state.currentMode } >
            { this.props.allowedModes.map( this.createModeNav ) }
          </TWBS.ButtonGroup>
        );
      }

      return (
        <div className="viewer">
          <TWBS.Navbar fluid className="viewer-nav">
            {/* Searchbox for Viewer (1) */}
            <TWBS.Input type = "text"
                        placeholder = "Search"
                        value = { this.state.searchString }
                        groupClassName = "navbar-form navbar-left"
                        onChange = { this.handleSearchChange }
                        addonBefore = { <Icon glyph ="search" /> } />

            {/* Select view mode (3) */}
            { viewerModeNav }

          </TWBS.Navbar>

          { this.createViewerContent() }
        </div>
      );
    }

});

export default Viewer;
