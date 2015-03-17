"use strict";

var React   =   require("react");

var Widget  =   require("../Widget");
var DummyWidgetContent = require("./DummyWidgetContent");

var SystemMiddleware = require("../../middleware/SystemMiddleware");
var SystemStore      = require("../../stores/SystemStore");

 function getSystemInfoFromStore( name ) {
 return SystemStore.getSystemInfo( name );
 }

var MemoryUtil = React.createClass({
  getInitialState: function() {
    return {
      statdResources:    [  {variable:"wiredData", dataSource:"localhost.memory.memory-wired.value", name:"Wired Memory", color:"#f39400"}
                           ,{variable:"cacheData", dataSource:"localhost.memory.memory-cache.value", name:"Cached Memory", color:"#8ac007"}
                           ,{variable:"activeData", dataSource:"localhost.memory.memory-active.value", name:"Active Memory", color:"#c9d200"}
                           ,{variable:"freeData", dataSource:"localhost.memory.memory-free.value", name:"Free Memory", color:"#5186ab"}
                           ,{variable:"inactiveData", dataSource:"localhost.memory.memory-inactive.value", name:"Inactive Memory", color:"#b6d5e9"}
                         ]
    , chartTypes:        []
    , ready:             false
    };
  }
, componentDidMount: function() {
    this.requestData();
    SystemStore.addChangeListener( this.handleChange );
    console.log("componentDidMount are we mounted? " + this.isMounted());
  }

, componentWillUnmount: function() {
    console.log("lets kill it!");
     SystemStore.removeChangeListener( this.handleChange );
  }

, requestData: function() {

    SystemMiddleware.requestSystemInfo( "hardware" );
  }
, primaryChart: function(type)
  {
    if (this.props.primary === undefined && type === "line")
    {
      return true;
    }
    else if (type === this.props.primary)
    {
      return true;
    }
    else
    {
      return false;
    }

  }
, handleChange: function() {
    console.log("handleChange are we mounted? " + this.isMounted());
    this.setState({ hardware  : getSystemInfoFromStore( "hardware" ) });
    if (this.state.hardware !== undefined)
     {
       var memSize = this.state.hardware["memory-size"];
       console.log(memSize);
       this.setState({  chartTypes:        [  {   type:"stacked"
                                                , primary: this.primaryChart("stacked")
                                                , y:function(d) { if(d === undefined) { return 0; } if (d[1] === "nan") { return null; } else { return (d[1]/1024)/1024; } }
                                              }
                                             ,{     type:"line"
                                                  , primary: this.primaryChart("line")
                                                  , y:function(d) { if(d[1] === "nan") { return null; } else { return (d[1]/memSize)*100; } }
                                                  , forceY:[0, 100]
                                                  , yUnit : "%"
                                              }
                                             ,{     type:"pie"
                                                  , primary: this.primaryChart("pie")
                                              }
                                           ]
                      , ready     :  true
                    });
      }
  }

, render: function() {
    if (this.state.ready === false)
    {
      console.log("not ready");
      console.log(this.state);
      return (
        <Widget
          positionX  =  {this.props.positionX}
          positionY  =  {this.props.positionY}
          title      =  {this.props.title}
          size       =  {this.props.size} >

          <div>Loading...</div>

        </Widget>
      );
    }
    console.log("ready");
    console.log(this.state);
    return (
      <Widget
        positionX  =  {this.props.positionX}
        positionY  =  {this.props.positionY}
        title      =  {this.props.title}
        size       =  {this.props.size} >

        <DummyWidgetContent
          statdResources    =  {this.state.statdResources}
          chartTypes        =  {this.state.chartTypes} >
        </DummyWidgetContent>


      </Widget>

    );
  }
});


module.exports = MemoryUtil;