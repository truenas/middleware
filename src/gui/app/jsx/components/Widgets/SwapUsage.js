/** @jsx React.DOM */

"use strict";

var React   =   require("react");

var Widget  =   require("../Widget");

var SwapUsage = React.createClass({
  getInitialState: function() {
    return {
      element:    ""
      ,tickCount: 0
    };
  },

  componentDidMount: function() {
    this.setState({
      element:    this.refs.svg.getDOMNode()
    });
    //console.log(this.state.element);
    this.drawChart();
  },

  exampleData: function() {
    return {
      "title":"Swap",    //Label the bullet chart
      "subtitle":"Usage",   //sub-label for bullet chart
      "ranges":[0,50,100],  //Minimum, mean and maximum values.
      "measures":[22],    //Value representing current measurement (the thick blue line in the example)
      "markers":[37]      //Place a marker on the chart (the white triangle marker)
    };
  },

  drawChart: function() {
      var chart = nv.models.bulletChart();

      chart.margin({top:25, right:20, bottom:0, left:50}) ;

      d3.select(this.state.element)
        .datum(this.exampleData())
        .transition().duration(300)
        .call(chart);

    //console.log(chart);

  },

  render: function() {
    var divStyle = {
      width: "100%",
      height: "100%",
      paddingTop: "25px"
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


module.exports = SwapUsage;