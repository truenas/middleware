// CHART HANDLER
// =============
// Mixin used to take the trouble of chart handling from individual widgets
// Remains of StatdWidgetContentHandler

"use strict";

import _ from "lodash";
import React from "react";
import moment from "moment";
import componentWidthMixin from "react-component-width-mixin";

import StatdMiddleware from "../../../middleware/StatdMiddleware";
import StatdStore from "../../../stores/StatdStore";

import Widget from "../../Widget";

var i = 0;

module.exports = {
    mixins: [ componentWidthMixin ]

  , getInitialState: function () {
      var initialStatdData = {};

      return {
          chart           : ""
        , stagedUpdate    : {}
        , graphType       : "line"
        , legendStateObj  : {}
        , legendStateArr  : []
        , errorMode       : false
        , statdData       : initialStatdData
        , statdDataLoaded : false
        , svgStyle        : {
                                width   : "calc(100% - 36px)"
                              , height  : ( this.props.dimensions[1] - 16 )
                              , "float" : "left"
                            }
        , divStyle        : {
                                width   : "36px"
                              , height  : "100%"
                              , "float" : "right"
                            }
      };
    }

  , componentDidMount: function () {
      StatdStore.addChangeListener( this.handleStatdChange );
      var newState = {};
      if ( this.state.statdResources.length > 0 ) {
        this.requestData();
        this.subscribeToUpdates();
      }

      if ( this.state.chartTypes.length > 0 ) {
        newState.graphType = _.result( _.findWhere( this.state.chartTypes, { "primary": true } ), "type" );
      }

      this.setState( newState );

    }

  , subscribeToUpdates: function () {
      StatdMiddleware.subscribeToPulse(
          this.state.widgetIdentifier
        , this.state.statdResources.map( this.createStatdSources )
      );
  }

  , requestData: function () {
    var stop  = moment();
    var start = moment().subtract( 15, "m" );

    _.forEach( this.state.statdResources, function ( resource ) {
      StatdMiddleware.requestWidgetData( resource.dataSource, start.format(),  stop.format(), "10S" );

    });

  }
  , componentDidUpdate: function ( prevProps, prevState ) {
      var newState = {};
      if ( this.state.statdResources.length !== prevState.statdResources.length ) {
        this.requestData();
        this.subscribeToUpdates();
      }

      if ( this.state.chartTypes.length !== prevState.chartTypes.length ) {
        newState.graphType = _.result( _.findWhere( this.state.chartTypes, { "primary": true } ), "type" );
      }

      this.setState( newState );

      // Only update if we have the required props, there is no staged update
      // currently being assembled, and we have access to both D3 and NVD3
      // (on the basis that the component is mounted)
      if ( this.isMounted() && this.state.chartTypes.length > 0 && this.state.statdDataLoaded ) {
        if ( !this.state.chart ) {
          this.drawChart();
        }
        var chartShouldReload = ( prevState.graphType !== this.state.graphType );
        //var statdDataExists = _.all( this.state.statdData, function( dataArray ) {
        //  return _.isArray( dataArray ) && dataArray.length > 0;
        //});

        if ( chartShouldReload ) {
          this.drawChart( chartShouldReload );
        } else if ( _.isEmpty( this.state.stagedUpdate ) &&
                    !_.isEmpty( prevState.stagedUpdate ) ) {
          this.drawChart();
        }

        if ( prevState.componentWidth !== this.state.componentWidth ) {
          //console.log("redraw");
          this.drawChart();
        }
      }
    }

  , shouldComponentUpdate: function ( nextProps, nextState ) {
      return nextState.statdResources   !==  this.state.statdResources    ||
             nextState.chartTypes       !==  this.state.chartTypes        ||
             nextState.statdDataLoaded  !==  this.state.statdDataLoaded   ||
             nextState.stagedUpdate     !==  this.state.stagedUpdate      ||
             nextState.graphType        !==  this.state.graphType         ||
             nextState.componentWidth   !==  this.state.componentWidth    ||
             nextProps.position         !==  this.props.position;
	}

  , componentWillUnmount: function () {
      StatdStore.removeChangeListener( this.handleStatdChange );
      StatdMiddleware.unsubscribeFromPulse(
          this.state.widgetIdentifier
        , this.state.statdResources.map( this.createStatdSources )
      );
    }

  , createStatdSources: function ( dataObject ) {
      return dataObject.dataSource;
    }

  , handleStatdChange: function () {
      var newState     = {};

      // Do we have initial stack of data?
      if ( this.state.statdDataLoaded === true ) {
        var dataUpdate   = StatdStore.getWidgetDataUpdate();
        var updateTarget = _.find(
            this.state.statdResources
          , function ( resource ) {
              return dataUpdate.name === "statd." + resource.dataSource + ".pulse";
            }
        );

        // Don't bother doing anything unless we have a valid target, based on
        // something in our statdResources. This means the widget won't update based
        // on pulse data intended for other widgets.
        if ( updateTarget && updateTarget["variable"] ) {
          var updateVariable = updateTarget["variable"];
          var stagedUpdate   = _.cloneDeep( this.state.stagedUpdate );
          var newDataPoint   = [ dataUpdate.args["timestamp"], dataUpdate.args["value"] ];

          // Ideally, each of the n responses will be sent one after another - if
          // they aren't, they should be queued up in stagedUpdate so that they can
          // be updated as a single batch - making sure the chart only re-renders when
          // all n of the specified data is available. This logic could be modified
          // to set a certain threshhold beyond which the chart would force an update
          // even if it was still waiting for one of the pulses, or it had receieved
          // five of one and only one of all the others, etc.

          // TODO: More clear business logic for data display

          if ( stagedUpdate[ updateVariable ] && _.isArray( stagedUpdate[ updateVariable ] ) ) {
            stagedUpdate[ updateVariable ].push( newDataPoint );
          } else {
            stagedUpdate[ updateVariable ] = [ newDataPoint ];
          }

          if ( _.keys( stagedUpdate ).length >= this.state.statdResources.length ) {
            newState.statdData = {};

            _.forEach( stagedUpdate, function ( data, key ) {
              var newData = this.state.statdData[ key ] ? this.state.statdData[ key ].concat( data ) : [];
              newState.statdData[ key ] = _.takeRight( newData, 100 );
            }.bind( this ) );
            stagedUpdate = {};
          }

          this.setState( _.merge(
              { "stagedUpdate": stagedUpdate }
            , newState
          ) );
        }
      } else {
        newState.statdData = {};
        _.forEach( this.state.statdResources,  function( resource ) {
          newState.statdData[ resource.variable ] = StatdStore.getWidgetData( resource.dataSource ) || [];

          if ( newState.statdData[ resource.variable ] && newState.statdData[ resource.variable ].error ) {
            newState.errorMode = true;
          }
        });

        newState.statdDataLoaded = _.all( newState.statdData, function( dataArray ) {
                                        return _.isArray( dataArray ) && dataArray.length > 0;
                                      });
        this.setState( newState );
      }
    }

  , drawChart: function ( chartShouldReload ) {
      var newState     = {};
      var chartSVGNode = this.refs.svg.getDOMNode();
      var xLabel;
      var yUnit;
      newState.legendStateArr =  this.state.legendStateArr;
      newState.legendStateObj =  this.state.legendStateObj;

      newState["chart"] = this.state.chart ? this.state.chart : null;

      if ( chartShouldReload ) {
        // Way how to make sure only the desired tooltips are displayed.
        d3.select( chartSVGNode )
          .on( "mousemove", null )
          .on( "mouseout", null )
          .on( "dblclick", null )
          .on( "click", null )
          .selectAll( "*" ).remove();

        newState["chart"] = null;
        newState.legendStateArr = [];
        newState.legendStateObj = {};
      }

      if ( newState["chart"] ) {
        // There is an existing representation of the chart, which has been
        // carried over from the previous state, and it should just be updated.
        d3.select( chartSVGNode )
          .datum( this.chartData( this.state.graphType ) )
          .call( newState["chart"] );

        if ( !_.isEmpty( newState.legendStateObj ) ) {
          if ( this.state.graphType === "pie" )	{
            newState["chart"].dispatch.changeState( { disabled: newState.legendStateObj } );
          } else {
            newState["chart"].dispatch.changeState( { disabled: newState.legendStateArr } );
          }

        } else {
          newState["chart"].update();
        }

      } else {
        // Either this is the first run, the chart type has changed, or something
        // else has happened to require a complete reload of the chart.
        var graphTypeObject = _.findWhere( this.state.chartTypes, { "type": this.state.graphType } );
        var newChart;

        switch ( this.state.graphType ) {

          case "stacked":
            newChart = nv.models.stackedAreaChart()
              .options({
                  margin                  : { top: 15, right: 40, bottom: 60, left: 60 }
                , x                       : graphTypeObject.x || function ( d ) { return d[0]; }   //We can modify the data accessor functions...
                , y                       : graphTypeObject.y || function ( d)  { return d[1]; }   //...in case your data is formatted differently.
                , transitionDuration      : 250
                , style                   : "Expanded"
                , showControls            : false       //Allow user to choose 'Stacked', 'Stream', 'Expanded' mode.
                , clipEdge                : false
                , useInteractiveGuideline : true    //Tooltips which show all data points. Very nice!
              });

            // chart sub-models (ie. xAxis, yAxis, etc) when accessed directly,
            // return themselves, not the parent chart, so need to chain separately
            xLabel = graphTypeObject.xLabel || "Time";
            newChart.xAxis
              .axisLabel( xLabel )
              .tickFormat( function ( d ) {
                return moment.unix( d ).format( "HH:mm:ss" );
              });

            yUnit = graphTypeObject.yUnit || "";
            newChart.yAxis
              .axisLabel( graphTypeObject.yLabel )
              .tickFormat( function ( d ) {
                return ( d + yUnit );
              });
            break;

          case "line":
            newChart = nv.models.lineChart()
            .options({
                margin                  : { top: 15, right: 40, bottom: 60, left: 60 }
              , x                       : graphTypeObject.x || function ( d ) { return d[0]; }
              , y                       : graphTypeObject.y || function ( d ) { return d[1]; }
              , showXAxis               : true
              , showYAxis               : true
              , transitionDuration      : 250
              , forceY                  : graphTypeObject.forceY //[0, 100]
              , useInteractiveGuideline : true
            });

            // chart sub-models (ie. xAxis, yAxis, etc) when accessed directly, return themselves, not the parent chart, so need to chain separately
            xLabel = graphTypeObject.xLabel || "Time";
            newChart.xAxis
              .axisLabel( xLabel )
              .tickFormat( function ( d ) {
                return moment.unix( d ).format( "HH:mm:ss" );
              });

            yUnit = graphTypeObject.yUnit || "";
            newChart.yAxis
              .axisLabel( graphTypeObject.yLabel )
              .tickFormat( function ( d ) {
                return ( d + yUnit );
              });
            break;

          case "pie":
            var colors = [];
            _.forEach( this.state.statdResources,  function ( resource ) {
              colors.push( resource.color );
            });
            newChart = nv.models.pieChart()
            .options({
                margin             : { top: 0, right: 0, bottom: 0, left: 0 }
              , x                  : graphTypeObject.x || function ( d ) { return d.label; }
              , y                  : graphTypeObject.y || function ( d ) { return d.value; }
              , color              : colors
              , showLabels         : true
              , labelThreshold     : 1
              , labelType          : "value" //Configure what type of data to show in the label. Can be "key", "value" or "percent"
              , transitionDuration : 250
              , donut              : false
              , donutRatio         : 0.35
            });
            break;

          default:
            console.log( this.state.graphType + " is not a supported chart type." );
            return;
        }
        var hndlChrtStChng = this.handleChartStateChange;
        newChart.dispatch.on( "stateChange", function ( e ) { hndlChrtStChng( e ); });
        newState["chart"] = newChart;

        d3.select( chartSVGNode )
          .datum( this.chartData( this.state.graphType ) )
          .call( newState["chart"] );

        // TODO: Figure out a good way to do this automatically
        // nv.utils.windowResize(chart.update);
        // nv.utils.windowResize(function() { d3.select('#chart1 svg').call(chart) });

        // chart.dispatch.on('stateChange', function(e) { nv.log('New State:', JSON.stringify(e)); });
      }

      this.setState( newState );
    }

  , handleChartStateChange: function( newChartState ) {
    var legendStateObject = {};
    var legendStateArray = newChartState["disabled"];

    for ( var i = 0; i < newChartState["disabled"].length; i++ ) {
      legendStateObject[i] = newChartState["disabled"][i];
    }

    this.setState( {   legendStateObj: legendStateObject
                     , legendStateArr: legendStateArray } );
    // console.log(legendStateObject);
  }

  , chartData: function ( chartType ) {
      var returnArray = [];
      var statdData   = this.state.statdData;

      switch ( chartType ) {
        case "line":
          _.forEach( this.state.statdResources, function ( resource ) {
            var returnArrayMember = {
                area   : resource.area || false
              , values : statdData[ resource.variable ]
              , key    : resource.name
              , color  : resource.color
            };
            returnArray.push( returnArrayMember );
          }.bind( this ) );
          break;

        case "stacked":
          _.forEach( this.state.statdResources, function ( resource ) {
            var returnArrayMember = {
                values : statdData[ resource.variable ]
              , key    : resource.name
              , color  : resource.color
            };
            returnArray.push( returnArrayMember );
          }.bind( this ) );
          break;

        case "pie":
          _.forEach( this.state.statdResources, function ( resource ) {
            var returnArrayMember = {
                value : statdData[ resource.variable ][ ( statdData[ resource.variable ].length - 1 ) ][1]
              , label : resource.name
            };
            returnArray.push( returnArrayMember );
          }.bind( this ) );
          break;

      }
      return returnArray;
    }

  , returnErrorMsgs: function ( resource, index ) {
      var errorMsg;
      var statdData = this.state.statdData;

      if ( statdData[ resource.variable ] && statdData[ resource.variable ].msg ) {
        errorMsg = resource.variable + ": " + statdData[ resource.variable ].msg;
      } else {
        errorMsg = "OK";
      }

      return (
        <div key={ index } >{ errorMsg }</div>
      );
    }

  , returnGraphOptions: function ( resource, index ) {
      var selectedGraphType = "";
      if ( resource.type === this.state.graphType ) {
        selectedGraphType = " selected";
      }
      return (
        <div
          key          = { index }
          className    = { "ico-graph-type-" + resource.type + selectedGraphType }
          onTouchStart = { this.toggleGraph }
          onClick      = { this.toggleGraph }>
            { resource.type }
        </div>
      );
    }

  , toggleGraph: function ( event ) {
      this.setState({ graphType: event.target.textContent });
    }

  , render: function () {
    if ( this.state.errorMode ) {
      return (
        <Widget
          dimensions  =  {this.props.dimensions}
          position    =  {this.props.position}
          title       = { this.props.title }
          size        = { this.props.size } >

          <div className="widget-error-panel">
              <h4>Something went sideways.</h4>
            { this.state.statdResources.map( this.returnErrorMsgs, this ) }
          </div>

      </Widget>
        );
    } else if ( this.state.statdDataLoaded && this.state.chartTypes.length > 0 ) {
      return (
        <Widget
          dimensions  =  {this.props.dimensions}
          position    =  {this.props.position}
          title     = { this.props.title }
          size      = { this.props.size } >

          <div className="widget-content">
            <svg ref="svg" style={this.state.svgStyle}></svg>
              <div ref="controls" style={this.state.divStyle}>
                { this.state.chartTypes.map( this.returnGraphOptions ) }
              </div>
          </div>

      </Widget>
        );
    } else {
      return (
        <Widget
          dimensions  =  {this.props.dimensions}
          position    =  {this.props.position}
          title     = { this.props.title }
          size      = { this.props.size } >

          <div className="widget-error-panel">
              <h4>Loading...</h4>
          </div>

      </Widget>
        );
    }
  }
};

