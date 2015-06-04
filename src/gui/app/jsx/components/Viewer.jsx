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
      { keyUnique           : React.PropTypes.string.isRequired
      , keyPrimary          : React.PropTypes.oneOfType(
                                [ React.PropTypes.number
                                , React.PropTypes.string
                                ]
                              )
      , keySecondary        : React.PropTypes.oneOfType(
                                [ React.PropTypes.number
                                , React.PropTypes.string
                                ]
                              )

      , searchKeys          : React.PropTypes.instanceOf( Set )

      , itemData            : React.PropTypes.oneOfType(
                                [ React.PropTypes.object
                                , React.PropTypes.array
                                ]
                              )
      , itemSchema          : React.PropTypes.object
      , itemLabels          : React.PropTypes.object

      , routeName           : React.PropTypes.string.isRequired
      , routeParam          : React.PropTypes.string.isRequired
      , routeNewItem        : React.PropTypes.string

      , textNewItem         : React.PropTypes.string.isRequired
      , textRemaining       : React.PropTypes.string.isRequired
      , textUngrouped       : React.PropTypes.string.isRequired

      , customDetailNavItem : React.PropTypes.func
      , customIconNavItem   : React.PropTypes.func

      , filtersInitial      : React.PropTypes.instanceOf( Set )
      , filtersAllowed      : React.PropTypes.instanceOf( Set )

      , groupsInitial       : React.PropTypes.instanceOf( Set )
      , groupsAllowed       : React.PropTypes.instanceOf( Set )

      , collapsedInitial    : React.PropTypes.instanceOf( Set )
      , collapsedAllowed    : React.PropTypes.instanceOf( Set )

      , columnsInitial      : React.PropTypes.instanceOf( Set )
      , columnsAllowed      : React.PropTypes.instanceOf( Set )

      // Viewer allows all modes by default. This list can be overwritten by
      // passing different  into your <Viewer />.
      // Allowed modes are:
      // detail : Items on left, with properties on right, configurable
      // icon   : Items as icons, with properties as modal
      // table  : Items as table rows, showing more data
      , modesInitial          : React.PropTypes.string
      , modesAllowed          : React.PropTypes.instanceOf( Set )
      , groupBy               : React.PropTypes.object
      }


  // REACT LIFECYCLE
  , getDefaultProps: function () {
      return (
        { keyPrimary       : ""
        , keySecondary     : ""

        , searchKeys       : new Set()

        , itemData         : {}
        , itemSchema       : null
        , itemLabels       : null

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
        { currentMode: this.changeViewerMode( this.props.modesInitial )
        , tableCols: this.props.columnsInitial
        , enabledGroups: this.props.groupsInitial
        , enabledFilters: this.props.filtersInitial
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
      this.processDisplayData({ itemData: nextProps.itemData });
    }


  // VIEWER DATA HANDLING

    // processDisplayData applys filters, searches, and then groups before
    // handing the data to any of its sub-views. The structure is deliberately
    // generic so that any sub-view may display the resulting data as it
    // sees fit.
  , processDisplayData: function ( options ) {
      let displayParams =
        _.assign( { itemData: this.props.itemData
                  , searchString: this.state.searchString
                  , enabledGroups: this.state.enabledGroups
                  , enabledFilters: this.state.enabledFilters
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
      if ( displayParams.enabledFilters.size > 0 ) {
        for ( let groupType of displayParams.enabledFilters ) {
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
      if ( displayParams.enabledGroups.size > 0 ) {
        for ( let groupType of displayParams.enabledGroups ) {
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
      this.setState({ currentMode: this.changeViewerMode( selectedKey ) });
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
      }

      return <ViewerContent
                tableCols = { this.state.tableCols }
                handleItemSelect = { this.handleItemSelect }
                selectedItem = { this.state.selectedItem }
                searchString = { this.state.searchString }
                filteredData = { this.state.filteredData }
                { ...this.props } />;
    }

  , render: function () {
      var viewerModeNav = null;

      // Create navigation mode icons
      if ( this.props.modesAllowed.size > 1 ) {
        viewerModeNav = (
          <TWBS.ButtonGroup
            className = "navbar-btn navbar-right"
            activeMode = { this.state.currentMode } >
            { [ ...this.props.modesAllowed ].map( this.createModeNav ) }
          </TWBS.ButtonGroup>
        );
      }

      return (
        <div className="viewer">
          <TWBS.Navbar fluid className="viewer-nav">
            {/* Searchbox for Viewer (1) */}
            <TWBS.Input
              type           = "text"
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

export default Viewer;
