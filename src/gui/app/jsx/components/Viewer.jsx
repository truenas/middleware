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

import DL from "../common/DebugLogger";
import Icon from "./Icon";
import DetailViewer from "./Viewer/DetailViewer";
import IconViewer from "./Viewer/IconViewer";
import TableViewer from "./Viewer/TableViewer";

// Main Viewer Wrapper Component
const Viewer = React.createClass(

  { mixins: [ viewerCommon ]

  // LIFECYCLE
  , getDefaultProps: function () {
      return (
        { keyUnique        : ""
        , keyPrimary       : ""
        , keySecondary     : ""

        , searchKeys       : new Set()

        , itemData         : {}
        , itemSchema       : null
        , itemLabels       : null

        , routeName        : ""
        , routeParam       : ""
        , routeNewItem     : ""

        , textNewItem      : ""
        , textRemaining    : ""
        , textUngrouped    : ""

        , filtersInitial   : new Set()
        , filtersAllowed   : null

        , groupsInitial    : new Set()
        , groupsAllowed    : null

        , collapsedInitial : new Set()
        , collapsedAllowed : null

        , columnsInitial   : new Set()
        , columnsAllowed   : null

        , modesInitial     : "detail"
        , modesAllowed     : new Set( [ "detail", "icon", "table" ] )

        , groupBy: {}
        }
      );
    }

  , getInitialState: function () {
      // Generate an array of keys which TableViewer can use to quickly generate
      // its internal structure by looping through the returned data from the
      // middleware and creating cells. Also useful for getting human-friendly
      // names out of the translation key.
      let currentParams = this.context.router.getCurrentParams();
      let selectedItem = currentParams[ this.props.routeParam ];

      return (
        { modeActive: this.changeViewerMode( this.props.modesInitial )
        , columnsEnabled: this.props.columnsInitial
        , groupsEnabled: this.props.groupsInitial
        , filtersEnabled: this.props.filtersInitial
        , filteredData: { grouped: false
                        , groups: []
                        , remaining: { entries: [] }
                        , rawList: []
                        }
        , searchString: ""
        , selectedItem: selectedItem
        }
      );
    }

  , componentWillReceiveProps: function ( nextProps ) {
      this.processDisplayData({ itemData: nextProps.itemData });
    }


  // DATA HANDLING

    // processDisplayData applys filters, searches, and then groups before
    // handing the data to any of its sub-views. The structure is deliberately
    // generic so that any sub-view may display the resulting data as it
    // sees fit.
  , processDisplayData: function ( options ) {
      let displayParams =
        _.assign( { itemData: this.props.itemData
                  , searchString: this.state.searchString
                  , groupsEnabled: this.state.groupsEnabled
                  , filtersEnabled: this.state.filtersEnabled
                  }
                  , options
                );

      // Prevent function from modifying nextProps
      let workingCollection = _.cloneDeep( displayParams.itemData );
      let filteredData = { grouped: false
                         , groups: []
                         , remaining: {}
                         , rawList: []
                         };

      // Reduce the array by applying exclusion filters (defined in the view)
      // TODO: Debug this - doesn't work right!
      if ( displayParams.filtersEnabled.size > 0 ) {
        for ( let groupType of displayParams.filtersEnabled ) {
          _.remove( workingCollection
                  , this.props.groupBy[ groupType ].testProp
                  );
        }
      }

      // Reduce the array to only items which contain a substring match for the
      // searchString in either their primary or secondary keys
      if ( this.props.searchKeys.size > 0 && displayParams.searchString ) {
        workingCollection =
          _.filter( workingCollection
                  , function performSearch ( item ) {
                      let searchTarget = "";

                      for ( let key of this.props.searchKeys ) {
                        searchTarget += Boolean( item[ key ] )
                      }

                      return (
                        _.includes( searchTarget.toLowerCase()
                                  , displayParams.searchString.toLowerCase()
                                  )
                      );
                    }.bind( this )
                  );
      }

      // At this point, workingCollection is an ungrouped (but filtered) list of
      // items, useful for views like the table.
      filteredData["rawList"] = _.clone( workingCollection );

      // Convert array into object based on groups
      if ( displayParams.groupsEnabled.size > 0 ) {
        for ( let groupType of displayParams.groupsEnabled ) {
          let groupData  = this.props.groupBy[ groupType ];
          let newEntries = _.remove( workingCollection, groupData.testProp );

          filteredData.groups.push(
            { name: groupData.name
            , key: groupType
            , entries: newEntries
            }
          );
        }

        filteredData["grouped"] = true;
      } else {
        filteredData["grouped"] = false;
      }

      // All remaining items are put in the "remaining" property
      filteredData["remaining"] =
        { name: filteredData["grouped"]
              ? this.props.textRemaining
              : this.props.textUngrouped
        , entries: workingCollection
        };

      this.setState(
        { filteredData: filteredData
        , searchString: displayParams.searchString
        , groupsEnabled: displayParams.groupsEnabled
        , filtersEnabled: displayParams.filtersEnabled
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
      let newMode;

      // See if a disallowed mode has been requested
      if ( this.props.modesAllowed.has( targetMode ) ) {
        newMode = targetMode;
      } else {
        newMode = this.props.modesInitial;
      }

      // When changing viewer modes, close any previously open items.
      // TODO: This may need to change with single-click select functionality.
      this.returnToViewerRoot();

      return newMode;
    }

  , handleModeSelect: function ( selectedKey, foo, bar ) {
      this.setState({ modeActive: this.changeViewerMode( selectedKey ) });
    }

  , changeTargetItem: function ( params ) {
      // Returns the first object from the input array whose selectionKey
      // matches the current route's dynamic portion. For instance,
      // "/accounts/users/root" with "bsdusr_usrname" as the selectionKey would
      // match the first object in itemData whose username === "root"
      return _.find( this.props.itemData
                   , function ( item ) {
                       return (
                         params[ this.props.routeParam ] ===
                         item[ this.props.keyUnique ]
                       );
                     }.bind( this )
                   );
    }


  // DISPLAY
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
          bsStyle = { ( mode === this.state.modeActive )
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
      const commonProps =
        { handleItemSelect : this.handleItemSelect

        , columnsEnabled   : this.state.columnsEnabled
        , selectedItem     : this.state.selectedItem
        , searchString     : this.state.searchString
        , filteredData     : this.state.filteredData
        }

      switch ( this.state.modeActive ) {

        default:
          DL.warn( "Viewer defaulting to default mode." );
          // Fall through to "detail".

        case "detail":
          ViewerContent = DetailViewer;
          break;

        case "icon":
          ViewerContent = IconViewer;
          break;

        case "table":
          ViewerContent = TableViewer;
          break;
      }

      return (
        <ViewerContent { ...commonProps } { ...this.props } />
      );
    }

  , render: function () {
      var viewDropdown   = null;
      var allowedFilters = this.props.displayData.allowedFilters;
      // var allowedGroups  = this.props.displayData.allowedGroups;
      var viewerModeNav  = null;

      // Create View Menu
      if ( allowedFilters ) {
      // if ( allowedFilters || allowedGroups ) {
        var menuSections = [];

        // Don't show grouping toggle for hidden groups
        // var visibleGroups = _.difference( this.props.displayData.allowedGroups, this.state.enabledFilters );

        if ( allowedFilters ) {
          this.createDropdownSection( menuSections, null, allowedFilters.map( this.createFilterMenuOption ) );
        }

        // if ( visibleGroups ) {
        //   this.createDropdownSection( menuSections, "Other Options", visibleGroups.map( this.createGroupMenuOption ) );
        // }


        viewDropdown = (
          <TWBS.DropdownButton title="View">
            { menuSections }
          </TWBS.DropdownButton>
        );
      } else {
        viewDropdown = (
          <TWBS.DropdownButton title="View" disabled />
        );
      }


      // Create navigation mode icons
      if ( this.props.modesAllowed.size > 1 ) {
        viewerModeNav = (
          <TWBS.ButtonGroup
            className = "navbar-btn navbar-right"
            activeMode = { this.state.modeActive } >
            { [ ...this.props.modesAllowed ].map( this.createModeNav ) }
          </TWBS.ButtonGroup>
        );
      }

      return (
        <div className="viewer">
          <TWBS.Navbar fluid className="viewer-nav">
            {/* Searchbox for Viewer */}
            <TWBS.Input
              type           = "text"
              placeholder    = "Search"
              groupClassName = "navbar-form navbar-left"
              value          = { this.state.searchString }
              onChange       = { this.handleSearchChange }
              addonBefore    = { <Icon glyph ="search" /> }
            />

            {/* Dropdown buttons (2) */}
            <TWBS.Nav className="navbar-left">
              {/* View Menu */}
              { viewDropdown }
            </TWBS.Nav>

            {/* Select view mode */}
            { viewerModeNav }

          </TWBS.Navbar>

          { this.createViewerContent() }
        </div>
      );
    }

});

export default Viewer;
