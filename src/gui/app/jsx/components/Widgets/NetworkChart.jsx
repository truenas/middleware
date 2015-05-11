

"use strict";

var React   =   require("react");

var Widget  =   require("../Widget");

var NetworkChart = React.createClass({
  getInitialState: function () {
    return {
      element:    ""
      ,tickCount: 0
    };
  },

  componentDidMount: function () {
    this.setState({
      element:    this.refs.svg.getDOMNode()
    });
    this.drawChart();
  },

  drawChart: function () {
    var chart;

    chart = nv.models.lineChart()
    .options({
      margin: {left: 100, bottom: 100},
      x: function(d,i) { return i},
      showXAxis: true,
      showYAxis: true,
      transitionDuration: 250
    });

  // chart sub-models (ie. xAxis, yAxis, etc) when accessed directly, return themselves, not the parent chart, so need to chain separately
  chart.xAxis
    .axisLabel("Time (s)")
    .tickFormat(d3.format(',.1f'));

  chart.yAxis
    .axisLabel('Bits per Secons (bps)')
    .tickFormat(d3.format(',.2f'));

  d3.select(this.state.element)
    .datum(this.sinAndCos())
    .call(chart);

  //TODO: Figure out a good way to do this automatically
  //nv.utils.windowResize(chart.update);
  //nv.utils.windowResize(function() { d3.select('#chart1 svg').call(chart) });

  chart.dispatch.on('stateChange', function(e) { nv.log('New State:', JSON.stringify(e)); });

  },

  sinAndCos: function () {
    var sin = [],
    cos = [],
    rand = [],
    rand2 = []
    ;

    for (var i = 0; i < 100; i++) {
      sin.push({x: i, y: i % 10 == 5 ? null : (Math.sin(i/10))*50 }); //the nulls are to show how defined works
      cos.push({x: i, y: .5 * Math.cos(i)});
      rand.push({x:i, y: Math.random() * (300) - 1 + 1});
      rand2.push({x: i, y: (Math.cos(i) * 33) + Math.random() / 10 })
    }

    return [
      {
        area: true,
        values: sin,
        key: "Total Traffic",
        color: "#ff7f0e"
      },
      {
        values: cos,
        key: "Interface 0",
        color: "#2ca02c"
      },
      {
        values: rand,
        key: "Interface 1",
        color: "#2222ff"
      }
      ,
      {
        values: rand2,
        key: "Random Cosine",
        color: "#667711"
      }
    ];
  },


  render: function () {
    return (
      <Widget
        positionX  =  {this.props.positionX}
        positionY  =  {this.props.positionY}
        title      =  {this.props.title}
        size       =  {this.props.size} >

        <svg ref="svg" width={500} height={500}></svg>

      </Widget>

    );
  }
});


module.exports = NetworkChart;
