"use strict";

var React   =   require("react");
var moment  =   require("moment");

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
       element        :   ""
      ,initialData    :   false
      ,chart          :   ""
      ,updateCounter  :   0
      ,graphType      :   "line"
    };
  }

 , componentDidMount: function() {
    this.requestWidgetData();

    StatdStore.addChangeListener( this.handleStatdChange );

    this.props.statdResources.forEach(function(resource) {
      StatdMiddleware.subscribe(resource.dataSource);
    });

    this.setState({
       element    :   this.refs.svg.getDOMNode()
      ,graphType  :   this.props.graphType
    });
 }

  , componentWillUnmount: function() {
    StatdStore.removeChangeListener( this.handleStatdChange );

    this.props.statdResources.forEach(function(resource) {
      StatdMiddleware.unsubscribe(resource.dataSource);
    });

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
      var state  = this.state;
      state.initialData = true;
      this.props.statdResources.forEach(function(resource) {
        state[resource.variable] = getWidgetDataFromStore( resource.dataSource );
        if (state[resource.variable] === undefined)
        {
          state.initialData = false;
        }
      });
      this.props.systemResources.forEach(function(resource) {
        state[resource.variable] = getSystemInfoFromStore( resource.dataSource );
        if (state[resource.variable] === undefined)
        {
          state.initialData = false;
        }
      });

      this.state = state;

      if (this.state.initialData === true )
      {
        this.drawChart();
      }
      console.log("1!");
    }
    else {
      console.log("2!");
      var ud = StatdStore.getWidgetDataUpdate();
      var updateCounter = this.state.updateCounter;
      var updateFunction = this.updateData;
      if (ud.name)
      {
        var updateArray = [ud.args["timestamp"], ud.args["value"]];
        this.props.statdResources.forEach(function(resource) {
          if (ud.name === "statd." + resource.dataSource + ".pulse")
          {
            updateCounter++;
            updateFunction(resource.variable, updateArray);
          }
        });

        if (updateCounter >= this.props.statdResources.length)
        {
          console.log("update");
          this.drawChart(true);
          updateCounter = 0;
        }
        this.state.updateCounter = updateCounter;
      }
    }

 }

 , requestWidgetData: function() {
    var stop = moment();
    var start = moment().subtract(15, "m");

    //console.log(start.format());
    //console.log(stop.format());
    this.props.statdResources.forEach(function(resource) {
      StatdMiddleware.requestWidgetData(resource.dataSource, start.format(),  stop.format(), "10S");
    });
    this.props.systemResources.forEach(function(resource) {
      SystemMiddleware.requestSystemInfo( resource.dataSource);
    });

  }

  , drawChart: function(update, reload) {
      if (reload === true)
      {
        this.state.element.innerHTML = null;
        this.state.chart = null;

        update = false;
      }

      if (update === true) {
          this.state.chart.update();
      }
      else {
        var chart;
        var memorySize = this.state.hardware["memory-size"];

        if (this.state.graphType === "stacked")
        {
          chart = nv.models.stackedAreaChart()
            .options({
               margin                     :    {top: 15, right: 50, bottom: 60, left: 60}
              ,x                          :    function(d) { if(d[0] === "nan") { return null; } else { return d[0]; } }   //We can modify the data accessor functions...
              ,y                          :    function(d) { if(d[1] === "nan") { return null; } else { return (d[1]/1024)/1024; } }   //...in case your data is formatted differently.
              ,useInteractiveGuideline    :    false    //Tooltips which show all data points. Very nice!
              ,transitionDuration         :    250
              ,style                      :    "Expanded"
              ,showControls               :    false       //Allow user to choose 'Stacked', 'Stream', 'Expanded' mode.
              ,clipEdge                   :    false
            });
        }
        else
        {
          chart = nv.models.lineChart()
          .options({
             margin                       :   {top: 15, right: 50, bottom: 60, left: 60}
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
      this.state.fullUpdate = false;
    }
  }

  , chartData: function() {
    var returnArray = [];
    var state = this.state;

    this.props.statdResources.forEach(function(resource) {
      var returnArrayMember = {
                                  area: false
                                , values: state[resource.variable]
                                , key: resource.name
                                , color: resource.color
                              };
      returnArray.push(returnArrayMember);
    });

    return returnArray;
  }

  ,togleGraph: function(e) {
    console.log(e.target.textContent);
    this.state.graphType = e.target.textContent;
    console.log(this.state.graphType);
    this.drawChart(false, true);
  }

  , render: function() {
    //console.log(this.state.widgetData);
    // <h3 style={elementStyle}>{"It works! "}{this.state.widgetData}</h3>
    var svgStyle = {
       width    : "calc(100% - 36px)"
      ,height   : "100%"
      ,"float"  : "left"
    };
    var divStyle = {
       width                : "36px"
      ,height               : "100%"
      ,"float"              : "right"
    };
    var returnGraphOptions = function(resource) {
                    return <div className={ "ico-graph-type-" + resource.type } onClick={ this.togleGraph }>{ resource.type }</div>;
                     };

    return (
      <div className="widget-content">
        <svg ref="svg" style={svgStyle}></svg>
        <div ref="controls" style={divStyle}>
          {this.props.chartTypes.map(returnGraphOptions, this)}
        </div>
      </div>
    );
  }
});


module.exports = DummyWidgetContent;