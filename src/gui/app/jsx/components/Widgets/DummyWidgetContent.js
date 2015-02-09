/** @jsx React.DOM */

"use strict";

var React   =   require("react");
var moment  =   require("moment");

var Widget  = 	require("../Widget");

var StatdMiddleware = require("../../middleware/StatdMiddleware");
var StatdStore      = require("../../stores/StatdStore");

function getWidgetDataFromStore( name ) {
 return StatdStore.getWidgetData( name );
 }

var DummyWidgetContent = React.createClass({
  getInitialState: function() {
    return {
       element      :   ""
      ,initialData  :   false
    };
  }

 , componentDidMount: function() {
    this.requestWidgetData();

    StatdStore.addChangeListener( this.handleStatdChange );
    StatdMiddleware.subscribe( "localhost.memory.memory-wired.value" );
    StatdMiddleware.subscribe( "localhost.memory.memory-cache.value" );

    this.setState({
      element:    this.refs.svg.getDOMNode()
    });
 }

  , componentWillUnmount: function() {
     StatdStore.removeChangeListener( this.handleStatdChange );
     StatdMiddleware.unsubscribe();
  }

  , updateData : function (target, updateArray) {

        var updatedData = this.state[target];
        updatedData.push(updateArray);
        if (updatedData.length > 100)
        {
          updatedData.shift();
        }

        this.setState({
          target: updatedData
          });

  }

 , handleStatdChange: function() {
    if ( this.state.initialData === false )
    {
      this.setState({  wiredData    :   getWidgetDataFromStore( "localhost.memory.memory-wired.value" )
                      ,cacheData    :   getWidgetDataFromStore( "localhost.memory.memory-cache.value" )
                    });
      if (this.state.wiredData !== undefined && this.state.cacheData !== undefined)
      {
        this.setState({  initialData  : true
                      });
        this.drawChart();
      }
      console.log("1!");
    }
    else {
      console.log("2!");
      var ud = StatdStore.getWidgetDataUpdate();
      var updateArray = [ud.args["timestamp"], ud.args["value"]];
      switch( ud.name )
      {
        case "statd.localhost.memory.memory-wired.value.pulse":
          this.updateData("wiredData", updateArray);
        break;
        case "statd.localhost.memory.memory-cache.value.pulse":
          this.updateData("cacheData", updateArray);
        break;

        default:
          // Do nothing
          console.log("This should not happened!");
      }
      this.drawChart();
    }

 }

 , requestWidgetData: function() {
    var stop = moment();
    var start = moment().subtract(15, "m");

    //console.log(start.format());
    //console.log(stop.format());
    StatdMiddleware.requestWidgetData( "localhost.memory.memory-wired.value", start.format(),  stop.format(), "10S");
    StatdMiddleware.requestWidgetData( "localhost.memory.memory-cache.value", start.format(),  stop.format(), "10S");
  }

  , drawChart: function() {
    var chart;

    chart = nv.models.lineChart()
    .options({
      margin: {left: 100, right: 30, bottom: 50},
      x: function(d) { if(d[0] === "nan") { return null; } else { return d[0]; } },
      y: function(d) { if(d[1] === "nan") { return null; } else { return d[1]; } },
      showXAxis: true,
      showYAxis: true,
      transitionDuration: 250
    });

  // chart sub-models (ie. xAxis, yAxis, etc) when accessed directly, return themselves, not the parent chart, so need to chain separately
  chart.xAxis
    .axisLabel("Time (s)")
    .tickFormat(d3.format(',.1f'));

  chart.yAxis
    .axisLabel("")
    .tickFormat(d3.format(',.2f'));

  d3.select(this.state.element)
    .datum(this.chartData())
    .call(chart);

  //TODO: Figure out a good way to do this automatically
  //nv.utils.windowResize(chart.update);
  //nv.utils.windowResize(function() { d3.select('#chart1 svg').call(chart) });

  chart.dispatch.on('stateChange', function(e) { nv.log('New State:', JSON.stringify(e)); });

  }

  , chartData: function() {
    return [
      {
        area: false,
        values: this.state.wiredData,
        key: "Wired Memory",
        color: "#ff7f0e"
      }
     ,{
        area: false,
        values: this.state.cacheData,
        key: "Cached Memory",
        color: "#8ac007"
      }
    ];
  }

  , render: function() {
    //console.log(this.state.widgetData);
    // <h3 style={elementStyle}>{"It works! "}{this.state.widgetData}</h3>
    var elementStyle = {
      margin: "0px",
      padding: "0px"
    };
    return (
      <Widget
    	   positionX  =  {this.props.positionX}
    	   positionY  =  {this.props.positionY}
    	   title      =  {this.props.title}
    	   size       =  {this.props.size} >

        <svg ref="svg" width={450} height={350}></svg>
      </Widget>
    );
  }
});


module.exports = DummyWidgetContent;