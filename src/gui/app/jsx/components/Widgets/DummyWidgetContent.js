/** @jsx React.DOM */

"use strict";

var React   =   require("react");
var moment  =   require("moment");

var Widget  = 	require("../Widget");

var StatdMiddleware = require("../../middleware/StatdMiddleware");
var StatdStore      = require("../../stores/StatdStore");

function getWidgetDataFromStore() {
 return StatdStore.getWidgetData();
 }

var DummyWidgetContent = React.createClass({
  getInitialState: function() {
    return {
       element:    ""
      ,widgetData: getWidgetDataFromStore()
    };
  }

 , componentDidMount: function() {
    this.requestWidgetData();

    StatdStore.addChangeListener( this.handleStatdChange );
    StatdMiddleware.subscribe();

    this.setState({
      element:    this.refs.svg.getDOMNode()
    });
 }

  , componentWillUnmount: function() {
     StatdStore.removeChangeListener( this.handleStatdChange );
     StatdMiddleware.unsubscribe();
  }

 , handleStatdChange: function() {
    if (this.state.widgetData.length < 1)
    {
      this.setState({ widgetData: getWidgetDataFromStore() });
      console.log("1!");
    } else {
      console.log("2!");
      var ud = StatdStore.getWidgetDataUpdate();
      var updateArray = [ud["timestamp"], ud["value"]];
      if (updateArray[0] !== undefined && updateArray[1] !== undefined)
      {
        var updatedData = this.state.widgetData;
        updatedData["data"].push(updateArray);
        updatedData["data"].shift();

        this.setState({
          widgetData: updatedData
          });
      }
    }
    this.drawChart();
    //console.log(ud);
 }

 , requestWidgetData: function() {
    var stop = moment();
    var start = moment().subtract(15, "m");

    //console.log(start.format());
    //console.log(stop.format());
    StatdMiddleware.requestWidgetData( "localhost.memory.memory-wired.value", start.format(),  stop.format(), "10S");
  }

  , drawChart: function() {
    var chart;

    chart = nv.models.lineChart()
    .options({
      margin: {left: 100, right: 30, bottom: 50},
      x: function(d) { if(d[0] === "nan") { return 0; } else { return d[0]; } },
      y: function(d) { if(d[1] === "nan") { return 0; } else { return d[1]; } },
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
    .datum(this.sinAndCos())
    .call(chart);

  //TODO: Figure out a good way to do this automatically
  //nv.utils.windowResize(chart.update);
  //nv.utils.windowResize(function() { d3.select('#chart1 svg').call(chart) });

  chart.dispatch.on('stateChange', function(e) { nv.log('New State:', JSON.stringify(e)); });

  }

  , sinAndCos: function() {
    return [
      {
        area: true,
        values: this.state.widgetData["data"],
        key: "Total Traffic",
        color: "#ff7f0e"
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