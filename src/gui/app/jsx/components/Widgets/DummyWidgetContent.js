/** @jsx React.DOM */

"use strict";

var React   =   require("react");
var moment  =   require("moment");

var Widget  = 	require("../Widget");

var StatdMiddleware = require("../../middleware/StatdMiddleware");
var StatdStore      = require("../../stores/StatdStore");

var SystemMiddleware = require("../../middleware/SystemMiddleware");
var SystemStore      = require("../../stores/SystemStore");

function getWidgetDataFromStore( name ) {
 return StatdStore.getWidgetData( name );
 }

 function getSystemInfoFromStore( name ) {
 return SystemStore.getSystemInfo( name );
 }

var DummyWidgetContent = React.createClass({
  getInitialState: function() {
    return {
       element      :   ""
      ,initialData  :   false
      ,chart        :   ""
    };
  }

 , componentDidMount: function() {
    this.requestWidgetData();

    StatdStore.addChangeListener( this.handleStatdChange );
    StatdMiddleware.subscribe( "localhost.memory.memory-wired.value" );
    StatdMiddleware.subscribe( "localhost.memory.memory-cache.value" );
    StatdMiddleware.subscribe( "localhost.memory.memory-active.value" );
    StatdMiddleware.subscribe( "localhost.memory.memory-free.value" );
    StatdMiddleware.subscribe( "localhost.memory.memory-inactive.value" );


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
      this.setState({  wiredData      :   getWidgetDataFromStore( "localhost.memory.memory-wired.value" )
                      ,cacheData      :   getWidgetDataFromStore( "localhost.memory.memory-cache.value" )
                      ,activeData     :   getWidgetDataFromStore( "localhost.memory.memory-active.value" )
                      ,freeData       :   getWidgetDataFromStore( "localhost.memory.memory-free.value" )
                      ,inactiveData   :   getWidgetDataFromStore( "localhost.memory.memory-inactive.value" )
                      ,hardware       :   getSystemInfoFromStore( "hardware" )
                    });
      if (this.state.wiredData !== undefined && this.state.cacheData !== undefined && this.state.activeData !== undefined && this.state.freeData !== undefined && this.state.inactiveData !== undefined && this.state.hardware !== undefined )
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
        case "statd.localhost.memory.memory-active.value.pulse":
          this.updateData("activeData", updateArray);
        break;
        case "statd.localhost.memory.memory-free.value.pulse":
          this.updateData("freeData", updateArray);
        break;
        case "statd.localhost.memory.memory-inactive.value.pulse":
          this.updateData("inactiveData", updateArray);
        break;

        default:
          // Do nothing
          console.log("This should not happened!");
      }
      this.drawChart(true);
    }

 }

 , requestWidgetData: function() {
    var stop = moment();
    var start = moment().subtract(15, "m");

    //console.log(start.format());
    //console.log(stop.format());
    StatdMiddleware.requestWidgetData( "localhost.memory.memory-wired.value", start.format(),  stop.format(), "10S");
    StatdMiddleware.requestWidgetData( "localhost.memory.memory-cache.value", start.format(),  stop.format(), "10S");
    StatdMiddleware.requestWidgetData( "localhost.memory.memory-active.value", start.format(),  stop.format(), "10S");
    StatdMiddleware.requestWidgetData( "localhost.memory.memory-free.value", start.format(),  stop.format(), "10S");
    StatdMiddleware.requestWidgetData( "localhost.memory.memory-inactive.value", start.format(),  stop.format(), "10S");

    SystemMiddleware.requestSystemInfo( "hardware" );

  }

  , drawChart: function(update) {
      if (update === true) {
          this.state.chart.update();
      }
      else {
        var chart;
        var memorySize = this.state.hardware["memory-size"];

        if (this.props.stacked)
        {
          chart = nv.models.stackedAreaChart()
            .options({
               margin                     :    {top: 15, right: 50, bottom: 60, left: 80}
              ,x                          :    function(d) { if(d[0] === "nan") { return null; } else { return d[0]; } }   //We can modify the data accessor functions...
              ,y                          :    function(d) { if(d[1] === "nan") { return null; } else { return (d[1]/1024)/1024; } }   //...in case your data is formatted differently.
              ,useInteractiveGuideline    :    true    //Tooltips which show all data points. Very nice!
              ,transitionDuration         :    500
              ,style                      :    "Expanded"
              ,showControls               :    false       //Allow user to choose 'Stacked', 'Stream', 'Expanded' mode.
              ,clipEdge                   :    false
            });
        }
        else
        {
          chart = nv.models.lineChart()
          .options({
             margin                       :   {top: 15, right: 50, bottom: 60, left: 50}
            ,x                            :   function(d) { if(d[0] === "nan") { return null; } else { return d[0]; } }
            ,y                            :   function(d) { if(d[1] === "nan") { return null; } else { return (d[1]/memorySize)*100; } }
            ,showXAxis                    :   true
            ,showYAxis                    :   true
            ,transitionDuration           :   250
            ,forceY                       :   [0, 100]
          });
        }

      // chart sub-models (ie. xAxis, yAxis, etc) when accessed directly, return themselves, not the parent chart, so need to chain separately
      chart.xAxis
        .axisLabel("Time")
        .tickFormat(function(d) {
              //console.log("plain: " + d + "formated: " + moment.unix(d).format("HH:mm:ss"));
              return moment.unix(d).format("HH:mm:ss");
        });

      chart.yAxis
        .axisLabel("")
        .tickFormat(function(d) {
              //console.log("plain: " + d + "formated: " + moment.unix(d).format("HH:mm:ss"));
              return (d + "%");
        });

      d3.select(this.state.element)
        .datum(this.chartData())
        .call(chart);

      //TODO: Figure out a good way to do this automatically
      //nv.utils.windowResize(chart.update);
      //nv.utils.windowResize(function() { d3.select('#chart1 svg').call(chart) });

      chart.dispatch.on('stateChange', function(e) { nv.log('New State:', JSON.stringify(e)); });
      this.state.chart = chart;
    }
  }

  , chartData: function() {
    return [
      {
        area: false,
        values: this.state.wiredData,
        key: "Wired Memory",
        color: "#f39400"
      }
     ,{
        area: false,
        values: this.state.cacheData,
        key: "Cached Memory",
        color: "#8ac007"
      }
     ,{
        area: false,
        values: this.state.activeData,
        key: "Active Memory",
        color: "#c9d200"
      }
     ,{
        area: false,
        values: this.state.freeData,
        key: "Free Memory",
        color: "#5186ab"
      }
     ,{
        area: false,
        values: this.state.inactiveData,
        key: "Inactive Memory",
        color: "#b6d5e9"
      }

    ];
  }

  , render: function() {
    //console.log(this.state.widgetData);
    // <h3 style={elementStyle}>{"It works! "}{this.state.widgetData}</h3>
    var divStyle = {
      width: "100%",
      height: "100%"
    };
    return (
      <Widget
        positionX  =  {this.props.positionX}
        positionY  =  {this.props.positionY}
        title      =  {this.props.title}
        size       =  {this.props.size} >

        <svg ref="svg" style={divStyle}></svg>

      </Widget>
    );
  }
});


module.exports = DummyWidgetContent;