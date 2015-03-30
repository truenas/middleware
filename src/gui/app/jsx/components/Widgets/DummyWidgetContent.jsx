"use strict";

var componentLongName = "DummyWidgetContent";

var _      = require("lodash");
var React  = require("react");
var moment = require("moment");

var StatdMiddleware = require("../../middleware/StatdMiddleware");
var StatdStore      = require("../../stores/StatdStore");

var svgStyle = {
    width   : "calc(100% - 36px)"
  , height  : "100%"
  , "float" : "left"
};

var divStyle = {
    width   : "36px"
  , height  : "100%"
  , "float" : "right"
};

var DummyWidgetContent = React.createClass({

    propTypes: {
        statdResources : React.PropTypes.array.isRequired
      , chartTypes     : React.PropTypes.array.isRequired
    }

  , getInitialState: function() {
      var initialStatdData = {};
      var initialErrorMode = false;

      this.props.statdResources.forEach( function( resource ) {
        initialStatdData[ resource.variable ] = StatdStore.getWidgetData( resource.dataSource ) || [];

        if ( initialStatdData[ resource.variable ] && initialStatdData[ resource.variable ].error ) {
          initialErrorMode = true;
        }

      });

      return {
          chart        : ""
        , stagedUpdate : {}
        , graphType    : "line"
        , errorMode    : false
        , statdData    : initialStatdData
      };
    }

  , componentDidMount: function() {
      var stop  = moment();
      var start = moment().subtract( 15, "m" );

      StatdStore.addChangeListener( this.handleStatdChange );

      this.props.statdResources.forEach( function( resource ) {
        StatdMiddleware.subscribe( componentLongName, resource.dataSource );
      });

      this.props.statdResources.forEach(function(resource) {
        StatdMiddleware.requestWidgetData( resource.dataSource, start.format(),  stop.format(), "10S" );
      });

      this.setState({
          graphType : _.result( _.findWhere( this.props.chartTypes, { "primary": true } ), "type" )
      });
    }

  , componentDidUpdate: function( prevProps, prevState ) {
      // Only update if we have the required props, and if there is no staged
      // updade currently being assembled
      if ( this.props.statdResources.length     &&
           this.props.chartTypes.length         &&
           _.isEmpty( this.state.stagedUpdate ) ){
        // FIXME: Temporarily disabled, since it recursively calls setState
        // this.drawChart();
      }
    }

  , componentWillUnmount: function() {
      StatdStore.removeChangeListener( this.handleStatdChange );

      this.props.statdResources.forEach( function( resource ) {
        StatdMiddleware.unsubscribe( componentLongName, resource.dataSource );
      });
    }

  , handleStatdChange: function() {
      var newState     = {};
      var dataUpdate   = StatdStore.getWidgetDataUpdate();
      var updateTarget = _.find(
            this.props.statdResources
          , function( resource ) {
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

        if ( _.keys( stagedUpdate ).length >= this.props.statdResources.length ) {
          _.each( stagedUpdate, function( data, key ) {
            if ( _.has( key, this.state.statdData ) ) {
              newState.statdData[ key ] = _.take( _.cloneDeep( this.state.statdData[ key ] )
                                 .push( stagedUpdate[ key ] ), 100 );
            }
          }.bind( this ) );

          stagedUpdate = {};
        }

        this.setState( _.merge(
            { "stagedUpdate": stagedUpdate }
          , newState
        ));
      }
    }

  , drawChart: function( update, reload ) {
      if (reload === true)
      {
        var elmnt = d3.select( this.refs.svg.getDOMNode() );
        // Way how to make sure only the desired tooltips are displayed.
        elmnt
          .on("mousemove", null)
          .on("mouseout", null)
          .on("dblclick", null)
          .on("click", null);
        elmnt.selectAll("*").remove();
        this.setState({chart : null});
        update = false;
      }

      if (update === true) {
        var chart = this.state.chart;
        d3.select( this.refs.svg.getDOMNode() )
        .datum(this.chartData(this.state.graphType))
        .call(chart);
        chart.update();
        this.setState({"chart" : chart});
        //this.state.chart.update();
      }
      else {
        var chart;
        var graphTypeObject;

        if (this.state.graphType === "stacked")
        {
          graphTypeObject = this.selectObjectFromArray(this.props.chartTypes, "stacked");
          chart = nv.models.stackedAreaChart()
            .options({
               margin                     :    {top: 15, right: 40, bottom: 60, left: 60}
              ,x                          :    graphTypeObject.x || function(d) { if(d[0] === "nan") { return null; } else { return d[0]; } }   //We can modify the data accessor functions...
              ,y                          :    graphTypeObject.y || function(d) { if(d[1] === "nan") { return null; } else { return d[1]; } }   //...in case your data is formatted differently.
              ,transitionDuration         :    250
              ,style                      :    "Expanded"
              ,showControls               :    false       //Allow user to choose 'Stacked', 'Stream', 'Expanded' mode.
              ,clipEdge                   :    false
              ,useInteractiveGuideline    :    true    //Tooltips which show all data points. Very nice!
            });

          // chart sub-models (ie. xAxis, yAxis, etc) when accessed directly, return themselves, not the parent chart, so need to chain separately
          var xLabel = graphTypeObject.xLabel || "Time";
          chart.xAxis
            .axisLabel(xLabel)
            .tickFormat(function(d) {
              return moment.unix(d).format("HH:mm:ss");
            });

          var yUnit = graphTypeObject.yUnit || "";
          chart.yAxis
            .axisLabel(graphTypeObject.yLabel)
            .tickFormat(function(d) {
              return (d + yUnit);
            });


        }
        else if (this.state.graphType === "line")
        {
          graphTypeObject = this.selectObjectFromArray(this.props.chartTypes, "line");
          chart = nv.models.lineChart()
          .options({
             margin                       :   {top: 15, right: 40, bottom: 60, left: 60}
            ,x                            :   graphTypeObject.x || function(d) { if(d[0] === "nan") { return null; } else { return d[0]; } }
            ,y                            :   graphTypeObject.y || function(d) { if(d[1] === "nan") { return null; } else { return d[1]; } }
            ,showXAxis                    :   true
            ,showYAxis                    :   true
            ,transitionDuration           :   250
            ,forceY                       :   graphTypeObject.forceY //[0, 100]
            ,useInteractiveGuideline      :   true
          });

          // chart sub-models (ie. xAxis, yAxis, etc) when accessed directly, return themselves, not the parent chart, so need to chain separately
          var xLabel = graphTypeObject.xLabel || "Time";
          chart.xAxis
            .axisLabel(xLabel)
            .tickFormat(function(d) {
              return moment.unix(d).format("HH:mm:ss");
            });

          var yUnit = graphTypeObject.yUnit || "";
          chart.yAxis
            .axisLabel(graphTypeObject.yLabel)
            .tickFormat(function(d) {
              return (d + yUnit);
            });



        }
        else if (this.state.graphType === "pie")
        {
          graphTypeObject = this.selectObjectFromArray(this.props.chartTypes, "pie");
          var colors = [];
          this.props.statdResources.forEach(function(resource) {
            colors.push(resource.color);
          });
          chart = nv.models.pieChart()
          .options({
             margin                       :   {top: 0, right: 0, bottom: 0, left: 0}
            ,x                            :   graphTypeObject.x || function(d) { return d.label; }
            ,y                            :   graphTypeObject.y || function(d) { if(d.value === "nan") { return 0; } else { return d.value; } }
            ,color                        :   colors
            ,showLabels                   :   true
            ,labelThreshold               :   1
            ,labelType                    :   "value" //Configure what type of data to show in the label. Can be "key", "value" or "percent"
            ,transitionDuration           :   250
            ,donut                        :   false
            ,donutRatio                   :   0.35
          });
        }
        else
        {
          console.log(this.state.graphType + " is not a supported chart type.");
          return;
        }

      d3.select( this.refs.svg.getDOMNode() )
        .datum(this.chartData(this.state.graphType))
        .call(chart);

      //TODO: Figure out a good way to do this automatically
      //nv.utils.windowResize(chart.update);
      //nv.utils.windowResize(function() { d3.select('#chart1 svg').call(chart) });

      //chart.dispatch.on('stateChange', function(e) { nv.log('New State:', JSON.stringify(e)); });
      this.setState({ "chart" : chart
                      ,fullUpdate : false });
    }
    }

  , chartData: function( chartType ) {
    var returnArray = [];
    var state = this.state;

    if (chartType === "line")
    {
      this.props.statdResources.forEach(function(resource) {
        var returnArrayMember = {
                                    area: resource.area || false
                                  , values: state[resource.variable]
                                  , key: resource.name
                                  , color: resource.color
                                };
        returnArray.push(returnArrayMember);
      });
    }
    else if (chartType === "stacked")
    {
      this.props.statdResources.forEach(function(resource) {
        var returnArrayMember = {
                                    values: state[resource.variable]
                                  , key: resource.name
                                  , color: resource.color
                                };
        returnArray.push(returnArrayMember);
      });
    }
    else if (chartType === "pie")
    {
      this.props.statdResources.forEach(function(resource) {
        var returnArrayMember = {
                                    value: state[resource.variable][state[resource.variable].length - 1][1]
                                  , label: resource.name
                                };
        returnArray.push(returnArrayMember);
      });
    }
    return returnArray;
    }

  , selectObjectFromArray: function( objectArray, valueToTest ) {
    var match = {};
    var i = 0;
    length = objectArray.length;

    for (; i < length; i++)
    {
      for (var property in objectArray[i])
      {
        if (objectArray[i][property] === valueToTest)
        {
          match = objectArray[i];
        }
      }
    }

    return match;
    }


  , returnErrorMsgs: function( resource, index ) {
      var errorMsg;

      if ( this.state[ resource.variable ] && this.state[ resource.variable ].msg ) {
        errorMsg = resource.variable + ": " + this.state[ resource.variable ].msg;
      } else {
        errorMsg = "OK";
      }

      return (
        <div key={ index } >{ errorMsg }</div>
      );
    }

  , returnGraphOptions: function( resource, index ) {
      return (
        <div
          key          = { index }
          className    = { "ico-graph-type-" + resource.type }
          onTouchStart = { this.togleGraph }
          onClick      = { this.togleGraph }>
            { resource.type }
        </div>
      );
    }

  , togleGraph: function(e) {
    var drwChrt = this.drawChart;
    this.setState({graphType : e.target.textContent}, function() { drwChrt(false, true); });
    }

  , render: function() {
      if ( this.state.errorMode ) {
        return (
          <div className="widget-error-panel">
            <h4>Something went sideways.</h4>
            { this.props.statdResources.map( this.returnErrorMsgs, this ) }
          </div>
        );
      } else {
        return (
          <div className="widget-content">
            <svg ref="svg" style={svgStyle}></svg>
            <div ref="controls" style={divStyle}>
              { this.props.chartTypes.map( this.returnGraphOptions ) }
            </div>
          </div>
        );
      }
    }

});

module.exports = DummyWidgetContent;
