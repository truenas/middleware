"use strict";

var React   =   require("react");

var ZfsMiddleware = require("../../middleware/ZfsMiddleware");
var ZfsStore      = require("../../stores/ZfsStore");

var chartHandler     = require("./mixins/chartHandler");

var DiskUsage = React.createClass({

  mixins: [ chartHandler ]

, getInitialState: function() {
    return {
        pool:              ZfsStore.getZfsPoolGetDisks( "freenas-boot")
      , statdResources:    []
      , chartTypes:        [  {   type:"line"
                                , primary: this.primaryChart("line")
                                , y:function(d) { if(d[1] === "nan") { return null; } else { return (Math.round((d[1]/1024) * 100) / 100); } }
                              }
                           ]
      , widgetIdentifier : "DiskUsage"
    };
  }

, componentDidMount: function() {
    ZfsStore.addChangeListener( this.handleChange );
    ZfsMiddleware.requestZfsPoolGetDisks( "freenas-boot" );
  }

, componentWillUnmount: function() {
    ZfsStore.removeChangeListener( this.handleChange );
  }

, handleChange: function() {
    var newState = {};
    newState.pool = ZfsStore.getZfsPoolGetDisks( "freenas-boot");

      console.log("pool");
      console.log(newState.pool);
    if (newState.pool)    {
      var systemPoolPath = newState.pool[0].split("/") ;
      var systemPoolName = systemPoolPath[systemPoolPath.length - 1].slice(0, systemPoolPath[systemPoolPath.length - 1].indexOf("p"));

          newState.statdResources = [  {variable:"write", dataSource:"localhost.disk-" + systemPoolName + ".disk_octets.write", name: systemPoolName + " Write", color:"#9ecc3c"}
                              , {variable:"read", dataSource:"localhost.disk-" + systemPoolName + ".disk_octets.read", name: systemPoolName + " Read", color:"#77c5d5"}
                           ];
      this.setState( newState );
    }


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

});


module.exports = DiskUsage;