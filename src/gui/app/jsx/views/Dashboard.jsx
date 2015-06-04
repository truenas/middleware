// Dashboard
// =========
// Default view for FreeNAS, shows overview of system and other general
// information.

"use strict";

import _ from "lodash";
import React from "react";

import freeNASUtil from "../common/freeNASUtil";

import ServicesMiddleware from "../middleware/ServicesMiddleware";
import ServicesStore from "../stores/ServicesStore";

import MemoryUtil from "../components/Widgets/MemoryUtil";
import CpuUtil from "../components/Widgets/CpuUtil";
import SystemInfo from "../components/Widgets/SystemInfo";
import SystemLoad from "../components/Widgets/SystemLoad";
import NetworkUsage from "../components/Widgets/NetworkUsage";
import DiskUsage from "../components/Widgets/DiskUsage";

const widgetSizes =
  {   "xs-square" : [ 75, 75 ]
    , "xs-rect"   : [ 165, 75 ]
    , "s-square"  : [ 165, 165 ]
    , "s-rect"    : [ 255, 165 ]
    , "sl-rect"   : [ 345, 165 ]
    , "m-square"  : [ 255, 255 ]
    , "m-rect"    : [ 345, 255 ]
    , "ml-rect"   : [ 435, 255 ]
    , "l-square"  : [ 345, 345 ]
    , "l-rect"    : [ 525, 345 ]
    , "xl-rect"   : [ 705, 525 ]
  };

const DragDropGrid = React.createClass({


  getDefaultProps: function () {
    return {
      // The size of each grid unit in pixels.
      gridSize   : 15
      // The amount of padding in grid units that should be in between any
      // two adjacent widgets.
      , gridGutter : 1
    };
  }

  , getInitialState: function () {
    return { movementMode: false }
  }

  ,  componentDidMount: function () {
      window.addEventListener( "mouseup", this.exitMovementMode );
      window.addEventListener( "resize", this.handleWindowResize );
      this.setState({
        gridWidth: this.calculateGridWidth()
      });
      this.initializeWidgets();
    }

  , componentWillUnmount: function () {
      window.removeEventListener( "mouseup", this.exitMovementMode );
      window.removeEventListener( "resize", this.handleWindowResize );
    }

  , componentWillReceiveProps: function ( nextProps ) {
    this.initializeWidgets( nextProps.children );
  }

  , handleWindowResize: function () {
    this.setState({
      gridWidth : this.calculateGridWidth()
    });
    this.initializeWidgets();

  }

  // Calculate how many grid units will fit in the window.
  ,  calculateGridWidth: function () {
      return this.toGridUnits( React.findDOMNode( this.refs.thePlayground )
                                    .offsetWidth );
    }

  // Converts pixels to grid units. Rounds down.
  , toGridUnits: function ( pixels ) {
      return Math.round( parseInt( pixels ) / this.props.gridSize );
    }

  // Converts grid units to pixels.
  , toPixels: function ( gridUnits ) {
      return gridUnits * this.props.gridSize;
    }

  // Begin moving a widget around. Records the id of the moving widget
  // and its starting location.

  , enterMovementMode: function ( id, event ) {
      this.setState({
        movementMode   : true
        , widgetInMotion : {
          id     : id
          , origin : [ event.nativeEvent.clientX, event.nativeEvent.clientY ]
        }
      });
    }

  , calculateMovement: function ( event ) {
      if ( this.state.movementMode ) {
        var newPos = [];
        var wim    = this.state.widgetInMotion;

        newPos[1] = this.toPixels(
            this.state.widgetMeta[ wim.id ].position[1] +
            this.toGridUnits( event.nativeEvent.clientY - wim.origin[1] )
            ) + "px";

        newPos[0] = this.toPixels(
            this.state.widgetMeta[ wim.id ].position[0] +
            this.toGridUnits( event.nativeEvent.clientX - wim.origin[0] )
            ) + "px";

        this.moveWidget( this.refs[ "widget-" + wim.id ].getDOMNode(), newPos );
      }
    }

  // When a widget is released from movement, change its location and move any
  // overlapping widgets out of the way.
  , exitMovementMode: function () {
      var movedWidget = document.querySelector( ".widget.in-motion" );
      var newState    = {};

      if ( movedWidget ) {
        var newPosition   = [ this.toGridUnits( movedWidget.style.left )
                            , this.toGridUnits( movedWidget.style.top )
                            ];
        var displayMatrix = _.clone( this.state.displayMatrix );
        var widgetMeta    = this.state.widgetMeta;
        var intersections;

        // Fill the moved widget's old spot with zeroes
        this.createMatrixFootprint(
            displayMatrix
          , widgetMeta[ this.state.widgetInMotion["id"] ]["position"]
          , widgetMeta[ this.state.widgetInMotion["id"] ]["size"]
          , 0
        );

        intersections = this.findIntersections(
            displayMatrix
          , newPosition
          , widgetMeta[ this.state.widgetInMotion["id"] ]["size"]
        );

        // Zero out the positions of the intersecting widgets
        for ( var i = 0; i < intersections.length; i++ ) {
          this.createMatrixFootprint(
              displayMatrix
            , widgetMeta[ intersections[i] ]["position"]
            , widgetMeta[ intersections[i] ]["size"]
            , 0
          );
        }

        // Identify and assign the new widget position
        widgetMeta[ this.state.widgetInMotion["id"] ]["position"] = newPosition;
        this.createMatrixFootprint(
            displayMatrix
          , newPosition
          , widgetMeta[ this.state.widgetInMotion["id"] ]["size"]
          , this.state.widgetInMotion["id"]
        );

        // Re-home the intersecting widgets
        for ( var i = 0; i < intersections.length; i++ ) {
          var newPos = this.findEmptySpace(
              displayMatrix
            , widgetMeta[ intersections[i] ]["size"]
          );

          widgetMeta[ intersections[i] ]["position"] = newPos;

          this.moveWidget(
              this.refs[ "widget-" + intersections[i] ].getDOMNode()
            , [ this.toPixels( newPos[0] ) + "px"
              , this.toPixels( newPos[1] ) + "px" ]
            , 350
          );
          this.createMatrixFootprint(
              displayMatrix
            , widgetMeta[ intersections[i] ]["position"]
            , widgetMeta[ intersections[i] ]["size"]
            , intersections[i]
          );
        }

        newState["displayMatrix"] = displayMatrix;
        newState["widgetMeta"]    = widgetMeta;
      }

      newState["movementMode"]   = false;
      newState["widgetInMotion"] = null;

      this.setState( newState );
    }

  // Animation for widget movement.
  , moveWidget: function ( widgetElement, newPos, duration ) {
      Velocity(
          widgetElement
        , {
          left   : newPos[0]
          , top  : newPos[1]
        }
        , {
          easing     : [ 0, 0.77, 0.47, 0.99 ]
          , duration : duration ? duration : 50
          , queue    : false
        });
    }

  // Add more space to the bottom of the grid. Used when a widget doesn't fit.
  , addEmptyRows: function ( displayMatrix, rows ) {
      for ( var i = 0; i < rows; i++ ) {
        displayMatrix.push( _.fill( Array( displayMatrix[0].length ), 0 ) );
      }
    }

  // Finds the first [x, y] position in the widget grid large enough to fit
  // a widget of the submitted size. Check is performed from left to right and
  // top to bottom.
  , findEmptySpace: function ( displayMatrix, dimensions ) {
      var newPos;
      var candidatePositions = [];

      // Check each existing row for a fit
      for ( var i = 0; i < displayMatrix.length; i++ ) {
        var candidateIndexes = [];

        // Check each y index in the row to test (in this order) that it:
        // 1. Is empty
        // 2. Is not too close to the end of the array for the widget to fit
        // 3. Is followed by sufficient empty space for the widget to fit
        for ( var j = 0; j < displayMatrix[i].length; j++ ) {
          if (
            displayMatrix[i][j] === 0 &&
            typeof displayMatrix[i][ j +
                                     dimensions[0] +
                                     this.props.gridGutter ] !== "undefined" &&
            _.every( displayMatrix[i]
             .slice( j
                    , j + dimensions[0] + this.props.gridGutter )
                    , function ( val ) { return val === 0; } )
          ) {
            // If all the condtions are met, push this index as a candidate.
            candidateIndexes.push( j );
          }
        }

        // If any candidates were found, push the array of candidates in this
        // row to the two-dimensional array of candidate positions.
        if ( candidateIndexes.length ) {
          candidatePositions.push( candidateIndexes );
        // If no candidates were found, push null to to the array of rows.
        // This makes it much easier to tell when a position is inviable during
        // the y-axis check.
        } else {
          candidatePositions.push( null );
        }
      }

      // Check if there's a suitable space by checking for x indicies that are
      // in sufficient subsequent rows.
      for ( var k = 0; k < candidatePositions.length; k++ ) {
        // Only check for shared candidate x indicies within the height needed
        // for the widget.
        var candidateRange = candidatePositions
                            .slice( k
                                    , k + dimensions[1]
                                        + this.props.gridGutter );
        var winners;

        // Make sure there are any candidate x indicies in this row to test.
        if ( _.isArray( candidatePositions[k] ) ) {
          // Only check for qualifying rows
          // if there are no null rows in the range
          if ( _.every( candidateRange, function ( entry ) {
            return _.isArray( entry );
          } ) ) {
            // If there's only one row with qualifiying indicies, you must be at
            // the bottom of the grid. Identify the first qualifiying x-index on
            // the bottom row as the winner. Extra vertical space is created
            // later in the function.
            if ( candidateRange.length === 1 ) {
              winners = [ candidateRange[0][0] ];
            // Find the x indicies that are in all the candidate rows. This
            // indicates that the entire range of rows has enough space for a
            // widget of this size.
            } else {
              winners = _.intersection.apply( this, candidateRange );
            }
          // If any rows in the range are not arrays (null), that means there's
          // no space at all for this widget in that row. At this point, you can
          // continue the loop with the next qualifying row, because this one
          // is certain to fail.
          } else {
            continue;
          }

          // If the intersection above produced any results, we have a winner.
          if ( winners.length ) {
            // It's possible for a winner to be too close to the bottom of the
            // grid to fit. In this case, add extra space.
            this.addEmptyRows( displayMatrix
                               , Math.max( 0
                                           , dimensions[1]
                                             + this.props.gridGutter
                                             - candidateRange.length ) );
            // Identify the actual new position as the first x-index in the
            // array of vertical intersections and leave the loop.
            newPos = [ winners[0], k ];
            break;
          // If the array of intersections was empty, there is not enough
          // vertical space in the candidate rows for this widget. Check for
          // candidates starting with the next row.
          } else {
            continue;
          }
        // If the reason there are no candidate x indicies to test in this row
        // is that there is no available space anywhere in the grid, add enough
        // rows to the grid to fit the entire widget and give the top left
        // coordinate of the new space as the new position.
        } else if ( candidatePositions.length - 1 === k ) {
          this.addEmptyRows( displayMatrix
                             , dimensions[1] + this.props.gridGutter );
          newPos = [ 0, candidatePositions.length ];
          break;
        // If the row is empty but not past the end of the grid,
        // try another row.
        } else {
          continue;
        }
      }

      return newPos;
    }

  // Find the positions where a widget of the specified position and
  // dimensions would intersect with another widget or its gutter.
  , findIntersections: function ( displayMatrix, position, dimensions ) {
      var intersections = [];

      for ( var i = position[1];
            i < position[1] + dimensions[1] + this.props.gridGutter;
            i++ ) {
        intersections.push( displayMatrix[i]
                            .slice( position[0]
                                    , position[0]
                                      + dimensions[0]
                                      + this.props.gridGutter ) );
      }

      return _.without( _.uniq( _.flattenDeep( intersections ) ), 0 );
    }

  , createMatrixFootprint: function ( displayMatrix
                                      , position
                                      , dimensions
                                      , fillEntry ) {
    for ( var i = position[1];
          i < position[1] + dimensions[1] + this.props.gridGutter;
          i++ ) {
      _.fill( displayMatrix[i]
              , fillEntry
              , position[0]
              , position[0] + dimensions[0] + this.props.gridGutter );
    }
  }

  // Used when a new set of widgets is requested to create random widgets and
  // distribute them around the page as necessary.
  , initializeWidgets: function ( chldrn ) {
      var children = chldrn || this.props.children;
      var widgetMeta = {};
      // The displayMatrix is a two-dimensional array in which empty positions
      // are represented as zeros and occupied ones are set to the UUID of the
      // widget occupying that space.
      var displayMatrix = [ _.fill( Array( this.calculateGridWidth() ), 0 ) ];

      React.Children.map( children, function ( Widget ) {
        var dimensions = [ this.toGridUnits( Widget.props.dimensions[0] )
                           , this.toGridUnits( Widget.props.dimensions[1] )
                         ];
        var position   = this.findEmptySpace( displayMatrix
                                              , dimensions );

        this.createMatrixFootprint( displayMatrix
                                    , position
                                    , dimensions
                                    , Widget.props.id );

        var widgetPosition  = [];
        widgetPosition[0]   = position[0];
        widgetPosition[1]   = position[1];

        widgetMeta[Widget.props.id] = {};
        widgetMeta[Widget.props.id].position = widgetPosition;
        widgetMeta[Widget.props.id].size = dimensions;
      }.bind( this ) )


      this.setState({
        displayMatrix : displayMatrix
        , widgetMeta  : widgetMeta
      });
    }

  , renderChildren: function () {
      if ( this.state.displayMatrix ) {
        return React.Children.map( this.props.children, function ( Widget ) {
          return React.cloneElement( Widget, {
            position: [
                        this.toPixels(
                            this.state.widgetMeta[Widget.props.id].position[0] )
                        , this.toPixels(
                            this.state.widgetMeta[Widget.props.id].position[1] )
                      ]
            , ref: "widget-" + Widget.props.id
            , onMouseDownHolder: this.enterMovementMode
                                 .bind( null, Widget.props.id )
            , inMotion: ( ( this.state.widgetInMotion &&
                            this.state.widgetInMotion.id ===
                            Widget.props.id )
                                                        ? true
                                                        : false )
          })
        }.bind( this ) )
      } else {
        return ( <div></div> )
      }

    }

  , render: function () {
    return (
      <main
        ref         = "thePlayground"
        onMouseMove = { this.calculateMovement }
        className   = { this.props.className + " playground grid-on" } >
          { this.renderChildren() }
      </main>
    );
  }

}
);

const Dashboard = React.createClass({

  getInitialState: function () {
      return {
        servicesList: ServicesStore.getAllServices()
        , sizeArr      : [ "s", "m", "l" ]
        , widgets      : {
          SystemInfo   : {
            id           : freeNASUtil.generateUUID()
            , dimensions : widgetSizes["m-rect"]
            , size       : "m-rect"
            , count      : 0
          }
          , MemoryUtil  : {
            id           : freeNASUtil.generateUUID()
            , dimensions : widgetSizes["m-rect"]
            , size       : "m-rect"
            , count      : 0
          }
          , CpuUtil     : {
            id           : freeNASUtil.generateUUID()
            , dimensions : widgetSizes["m-rect"]
            , size       : "m-rect"
            , count      : 0
          }
          , SystemLoad  : {
            id           : freeNASUtil.generateUUID()
            , dimensions : widgetSizes["m-rect"]
            , size       : "m-rect"
            , count      : 0
          }
          , NetworkUsage: {
            id           : freeNASUtil.generateUUID()
            , dimensions : widgetSizes["l-rect"]
            , size       : "l-rect"
            , count      : 0
          }
          , DiskUsage   : {
            id           : freeNASUtil.generateUUID()
            , dimensions : widgetSizes["l-rect"]
            , size       : "l-rect"
            , count      : 0
          }
        }
      };
    }

  , componentDidMount: function () {
      ServicesMiddleware.requestServicesList();
      ServicesStore.addChangeListener( this.handleServicesChange );
    }

  , componentWillUnmount: function () {
      ServicesStore.removeChangeListener( this.handleServicesChange );
    }

  , handleServicesChange: function () {
      this.setState({
        servicesList: ServicesStore.getAllServices()
      });
    }

  , changeSize: function ( widgtName ) {
    var newWidgetsState = this.state.widgets;
    var i = ( this.state.widgets[ widgtName ].count
              < this.state.sizeArr.length
              ? this.state.widgets[ widgtName ].count
              : 0 );
    i++;
    newWidgetsState[ widgtName ].count = i;
    newWidgetsState[ widgtName ].size = this.state.sizeArr[ i - 1 ]
                                 + this.state.widgets[ widgtName ].size
                                   .substring( 1
                                               , this.state.widgets[ widgtName ]
                                                       .size
                                                       .length );
    newWidgetsState[ widgtName ].dimensions =
    widgetSizes[ newWidgetsState[ widgtName ].size ];

    this.setState( { widgets: newWidgetsState } );
  }

  // TODO:
  // Maybe this should be moved into some kind of utility class, and generalized
  , isServiceRunning: function ( service ) {
      return ( _.findIndex( this.state.servicesList
                            , { name: service, state: "running" } ) > -1 );
    }

  , render: function () {
      if ( this.isServiceRunning( "collectd" ) === true ) {
        return (
              <DragDropGrid className = "widget-wrapper" >

                <SystemInfo
                  stacked           = "true"
                  title             = "System Info"
                  size              = { this.state.widgets.SystemInfo.size }
                  changeSize        = { this.changeSize
                                        .bind( this, "SystemInfo" )}
                  ref               = { "widget-"
                                        + this.state.widgets.SystemInfo.id }
                  dimensions        = { this.state.widgets
                                        .SystemInfo.dimensions }
                  position          = { this.state.widgets.SystemInfo.position }
                  id                = { this.state.widgets.SystemInfo.id } />

                <MemoryUtil
                  title = "Memory Value"
                  size  = { this.state.widgets.MemoryUtil.size }
                  changeSize = { this.changeSize
                                 .bind( this, "MemoryUtil" )}
                  dimensions  = { this.state.widgets.MemoryUtil.dimensions }
                  position    = { this.state.widgets.MemoryUtil.position }
                  id          = { this.state.widgets.MemoryUtil.id }  />

                <CpuUtil
                  primary = "pie"
                  title = "CPU utilization"
                  size  = { this.state.widgets.CpuUtil.size }
                  changeSize = { this.changeSize
                                 .bind( this, "CpuUtil" )}
                  dimensions  = { this.state.widgets.CpuUtil.dimensions }
                  position    = { this.state.widgets.CpuUtil.position }
                  id          = { this.state.widgets.CpuUtil.id }  />

                <SystemLoad
                  primary   = "stacked"
                  title     = "System Load"
                  size      = { this.state.widgets.SystemLoad.size }
                  changeSize = { this.changeSize
                                 .bind( this, "SystemLoad" )}
                  dimensions  = { this.state.widgets.SystemLoad.dimensions }
                  position    = { this.state.widgets.SystemLoad.position }
                  id          = { this.state.widgets.SystemLoad.id }  />

                <NetworkUsage
                  title = "Network Usage"
                  size  = { this.state.widgets.NetworkUsage.size }
                  changeSize = { this.changeSize
                                 .bind( this, "NetworkUsage" )}
                  graphType = "line"
                  dimensions  = { this.state.widgets.NetworkUsage.dimensions }
                  position    = { this.state.widgets.NetworkUsage.position }
                  id          = { this.state.widgets.NetworkUsage.id }  />

                <DiskUsage
                  title = "Disk Usage"
                  size  = { this.state.widgets.DiskUsage.size }
                  changeSize = { this.changeSize
                                 .bind( this, "DiskUsage" )}
                  graphType = "line"
                  dimensions  = { this.state.widgets.DiskUsage.dimensions }
                  position    = { this.state.widgets.DiskUsage.position }
                  id          = { this.state.widgets.DiskUsage.id }  />
              </DragDropGrid>
        );
      } else {
        return (
          <main>
            <h2>Dashboard View</h2>
            <h3>Please enable collectd service to display widgets.</h3>
          </main>
        );
      }
    }

});

export default Dashboard;
