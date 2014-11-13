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
      WarningBoxState: "hidden"
    };
  },

  handleBox: function(e) {

    if (this.state.WarningBoxState === "hidden")
    {      
      this.setState({ WarningBoxState: "visible" });
    }
    else
    {
      this.setState({ WarningBoxState: "hidden" });
    }
  },
  render: function() {
    return (
      <div>
      <div className = "notificationBar">
       <WarningBox boxState={this.state.WarningBoxState}/>
      


        <div className="userInfo">        
        <span onClick={this.handleBox}> <Icon glyph="warning" icoClass="icoAlert" icoSize="3x" warningFlag="1" /></span>        
        <Icon glyph="info-circle" icoClass="icoInfo" icoSize="3x" warningFlag="2" />
        <Icon glyph="list-alt" icoClass="icoQueue" icoSize="3x" warningFlag="3" />
        <Icon glyph = "user" icoSize = "2x" />
        <span className="userName">Kevin Spacey</span>
        

        </div>
      </div>
      <LeftMenu />
      <TWBS.Grid fluid className="mainGrid">
        {/* TODO: Add Modal mount div */}
        <TWBS.Row>
          {/* Primary view */}
          <TWBS.Col xs={9} sm={9} md={9} lg={9} xl={9}
                    xsOffset={1} smOffset={1} mdOffset={1} lgOffset={1} xlOffset={1}>
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