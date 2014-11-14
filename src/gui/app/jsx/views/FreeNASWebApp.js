/** @jsx React.DOM */

// Main App Wrapper
// ================
// Top level controller-view for FreeNAS webapp
"use strict";


var React  = require("react");

// Page router
var Router = require("react-router");
var Link   = Router.Link;

var Icon   = require("../components/Icon");
var LeftMenu   = require("../components/LeftMenu");
var WarningBox   = require("../components/WarningBox");
var QueueBox   = require("../components/QueueBox");
var InfoBox   = require("../components/InfoBox");
// Twitter Bootstrap React components
var TWBS   = require("react-bootstrap");

var FreeNASWebApp = React.createClass({
  getInitialState: function() {
    return {
      warningBoxIsVisible: 0,
      infoBoxIsVisible: 0,
      queueBoxIsVisible: 0,
      gridClass: "collapsed"
    };
  },

  handleBox: function(event) {
    //ultimate if  
    //this.setState({ warningBoxIsVisible: ((event.currentTarget.className.indexOf("icoAlert") > -1)? ((this.state.warningBoxIsVisible) ? 0 : 1) :  0) });

    if(event.currentTarget.className.indexOf("icoQueue") > -1){
      if (this.state.queueBoxIsVisible === 0){      
        this.setState({ infoBoxIsVisible: 0 });
        this.setState({ warningBoxIsVisible: 0 });
        this.setState({ queueBoxIsVisible: 1 });
      }else{
        this.setState({ queueBoxIsVisible: 0 });    
      }
    }
    if(event.currentTarget.className.indexOf("icoAlert") > -1){
      if (this.state.warningBoxIsVisible === 0){      
        this.setState({ infoBoxIsVisible: 0 });
        this.setState({ warningBoxIsVisible: 1 });
        this.setState({ queueBoxIsVisible: 0 });
      }else{
        this.setState({ warningBoxIsVisible: 0 });    
      }
    }
    if(event.currentTarget.className.indexOf("icoInfo") > -1){
      if (this.state.infoBoxIsVisible === 0){      
        this.setState({ infoBoxIsVisible: 1 });
        this.setState({ warningBoxIsVisible: 0 });
        this.setState({ queueBoxIsVisible: 0 });
      }else{
        this.setState({ infoBoxIsVisible: 0 });     
      }
    }

    
  },
  menuChange: function(gClass) {
    if (gClass === "expanded")
    {
      Velocity(this.refs.gridRef.getDOMNode()
      , { paddingLeft: "54px;" }
      , { duration: 1500,
          easing: "easeInOutBounce",
          complete: this.setState({ gridClass: gClass }) 
        }
      );
    }
    else
    {
      Velocity(this.refs.gridRef.getDOMNode()
      , { paddingLeft: "240px;" }
      , { duration: 1500,
          easing: "easeInOutBounce",
          complete: this.setState({ gridClass: gClass }) 
        }
      );
    }

    
  },

  render: function() {
    return (
      <div>
      <div className = "notificationBar">
       <WarningBox isVisible = {this.state.warningBoxIsVisible} />
       <InfoBox isVisible = {this.state.infoBoxIsVisible} />
       <QueueBox isVisible = {this.state.queueBoxIsVisible} />
      


        <div className="userInfo">        
        <Icon glyph="warning" icoClass="icoAlert" icoSize="3x" warningFlag="1" onClick={this.handleBox} />
        <Icon glyph="info-circle" icoClass="icoInfo" icoSize="3x" warningFlag="2" onClick={this.handleBox} />
        <Icon glyph="list-alt" icoClass="icoQueue" icoSize="3x" warningFlag="3" onClick={this.handleBox} />
        <Icon glyph = "user" icoSize = "2x" />

         <TWBS.SplitButton title="Kevin Spacey" pullRight>
          <TWBS.MenuItem key="1">Action</TWBS.MenuItem>
          <TWBS.MenuItem key="2">Another action</TWBS.MenuItem>
          <TWBS.MenuItem key="3">Something else here</TWBS.MenuItem>
          <TWBS.MenuItem divider />
          <TWBS.MenuItem key="4">Logout</TWBS.MenuItem>
        </TWBS.SplitButton>
          
        </div>
      </div>
      <LeftMenu handleMenuChange={this.menuChange} />
      <TWBS.Grid fluid ref="gridRef" className={"mainGrid " + this.state.gridClass}>
        {/* TODO: Add Modal mount div */}
        <TWBS.Row>
          {/* Primary view */}
          <TWBS.Col xs={12} sm={12} md={12} lg={12} xl={12} xsOffset={0} smOffset={0} mdOffset={0} lgOffset={0} xlOffset={0}>
            <h1>FreeNAS WebGUI</h1>
            { this.props.activeRouteHandler() }
          </TWBS.Col>

          {/* Tasks and active users */}
          <TWBS.Col xs={2} sm={2} md={2} lg={2} xl={2}>
            {/* TODO: Add tasks/users component */}
          </TWBS.Col>
        </TWBS.Row>
      </TWBS.Grid>
      </div>
    );
  }
});

module.exports = FreeNASWebApp;