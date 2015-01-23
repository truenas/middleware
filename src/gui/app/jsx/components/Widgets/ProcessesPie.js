/** @jsx React.DOM */

"use strict";

var React   =   require("react");
var d3      =   require("d3");

var Widget  =   require("../Widget");

var ProcessesPie = React.createClass({
  getInitialState: function() {
    return {
      element:    ""
      ,tickCount: 0
    };
  },

  componentDidMount: function() {
    this.setState({
      element:    this.refs.pieDiv.getDOMNode()
    });
    this.drawChart();
  },

  drawChart: function() {
    var w = 345;
    var h = 345;
    var r = (h/2)-5;
    //var color = d3.scale.category10();
    var color = d3.scale.ordinal()
    .domain(["Blocked", "Zombies", "Stopped", "Running", "Sleeping", "Idle", "Wait" ])
    .range(["#ff00ff", "#ff0000" , "#a000a0" , "#00e000" , "#0000ff" , "#574000" , "#000000"]);


    var data = [ {"label":"Blocked", "value":3}
                ,{"label":"Zombies", "value":1}
                ,{"label":"Stopped", "value":4}
                ,{"label":"Running", "value":12}
                ,{"label":"Sleeping", "value":18}
                ,{"label":"Idle", "value":2}
                ,{"label":"Wait", "value":7}];


    var vis = d3.select(this.state.element).append("svg:svg").data([data]).attr("width", w).attr("height", h).append("svg:g").attr("transform", "translate(" + (r+5) + "," + (r+5) + ")");
    var pie = d3.layout.pie().value(function(d){return d.value;});

    // declare an arc generator function
    var arc = d3.svg.arc().outerRadius(r);

    // select paths, use arc generator to draw
    var arcs = vis.selectAll("g.slice").data(pie).enter().append("svg:g").attr("class", "slice");
    arcs.append("svg:path")
        .attr("fill", function(d, i){
            return color(d.data.label);
        })
        .attr("d", function (d) {
            return arc(d);
        });

    // add the text
    arcs.append("svg:text").attr("fill", "#FFFFFF").attr("transform", function(d){
          d.innerRadius = 0;
          d.outerRadius = r;
          //console.log(d);
          //console.log(arc);
        return "translate(" + arc.centroid(d) + ")";}).attr("text-anchor", "middle").text( function(d, i) {
        return data[i].label;}
        );

  },

  render: function() {
    return (
      <Widget
        positionX  =  {this.props.positionX}
        positionY  =  {this.props.positionY}
        title      =  {this.props.title}
        size       =  {this.props.size} >

        <div ref="pieDiv"></div>

      </Widget>

    );
  }
});


module.exports = ProcessesPie;