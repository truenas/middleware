"use strict";

var React   =   require("react");

var Widget  =   require("../Widget");
var DummyWidgetContent = require("./DummyWidgetContent");

var MemoryUtil = React.createClass({
  getInitialState: function() {
    return {
      statdResources:    [  {variable:"wiredData", dataSource:"localhost.memory.memory-wired.value", name:"Wired Memory", color:"#f39400"}
                           ,{variable:"cacheData", dataSource:"localhost.memory.memory-cache.value", name:"Cached Memory", color:"#8ac007"}
                           ,{variable:"activeData", dataSource:"localhost.memory.memory-active.value", name:"Active Memory", color:"#c9d200"}
                           ,{variable:"freeData", dataSource:"localhost.memory.memory-free.value", name:"Free Memory", color:"#5186ab"}
                           ,{variable:"inactiveData", dataSource:"localhost.memory.memory-inactive.value", name:"Inactive Memory", color:"#b6d5e9"}
                         ]

    , systemResources:   [  {variable:"hardware", dataSource:"hardware", subArray:"memory-size"}
                         ]

    , chartTypes:        [  {   type:"stacked"
                              , primary:true
                              , y:function(d) { if(d[1] === "nan") { return null; } else { return (d[1]/1024)/1024; } }
                            }
                           ,{     type:"line"
                                , primary:false
                                , y:function(d) { if(d[1] === "nan") { return null; } else { return (d[1]/17143758848)*100; } }
                                , forceY:[0, 100]
                                , yUnit : "%"
                            }
                           ,{     type:"pie"
                                , primary:false
                            }
                         ]
    };
  }


, render: function() {
    return (
      <Widget
        positionX  =  {this.props.positionX}
        positionY  =  {this.props.positionY}
        title      =  {this.props.title}
        size       =  {this.props.size} >

        <DummyWidgetContent
          statdResources    =  {this.state.statdResources}
          systemResources   =  {this.state.systemResources}
          chartTypes        =  {this.state.chartTypes} >
        </DummyWidgetContent>


      </Widget>

    );
  }
});


module.exports = MemoryUtil;