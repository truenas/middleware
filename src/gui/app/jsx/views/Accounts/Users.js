/** @jsx React.DOM */

// Users
// =====
// Viewer for FreeNAS user accounts and built-in system users.

"use strict";


var React      = require("react");
var TWBS       = require("react-bootstrap");

var Viewer     = require("../../components/Viewer");
var editorUtil = require("../../components/Viewer/Editor/editorUtil");


// Dummy data from API call on relatively unmolested system
// TODO: Update to use data from Flux store
var inputData  = require("../../../data/fakedata/accounts.json");
var formatData = require("../../../data/middleware-keys/accounts-display.json")[0];
var itemData = {
    "route" : "users-editor"
  , "param" : "userID"
};

var UserView = React.createClass({
    propTypes: {
      item: React.PropTypes.object.isRequired
    }
  , render: function() {
    return (
      <TWBS.Grid fluid>
        {/* "Edit User" Button - Top */}
        <TWBS.Row>
          <TWBS.Col xs={12}>
            <TWBS.Button className = "pull-right"
                         bsStyle   = "info" >{"Edit User"}</TWBS.Button>
          </TWBS.Col>
        </TWBS.Row>

        {/* User icon and general information */}
        <TWBS.Row>
          <TWBS.Col xs={3}>
            <p>User Icon</p>
          </TWBS.Col>
          <TWBS.Col xs={9}>
            <h3>{ this.props.item["bsdusr_username"] }</h3>
            <h4 className="text-muted">{ editorUtil.writeString( this.props.item["bsdusr_full_name"], "\u200B" ) }</h4>
            <h4 className="text-muted">{ editorUtil.writeString( this.props.item["bsdusr_email"], "\u200B" ) }</h4>
            <hr />
          </TWBS.Col>
        </TWBS.Row>

        {/* Primary user data overview */}
        <TWBS.Row>
          <editorUtil.DataCell title = { "User ID" }
                               entry = { this.props.item["bsdusr_uid"] } />
          <editorUtil.DataCell title = { "Primary Group" }
                               entry = { this.props.item["bsdusr_group"] } />
          <editorUtil.DataCell title = { "Shell" }
                               entry = { this.props.item["bsdusr_shell"] } />
          <editorUtil.DataCell title = { "Locked Account" }
                               entry = { this.props.item["bsdusr_locked"] } />
          <editorUtil.DataCell title = { "Sudo Access" }
                               entry = { this.props.item["bsdusr_sudo"] } />
          <editorUtil.DataCell title = { "Password Disabled" }
                               entry = { this.props.item["bsdusr_password_disabled"] } />
        </TWBS.Row>

        {/* "Edit User" Button - Bottom */}
        <TWBS.Row>
          <TWBS.Col xs={12}>
            <TWBS.Button className = "pull-right"
                         bsStyle   = "info" >{"Edit User"}</TWBS.Button>
          </TWBS.Col>
        </TWBS.Row>
      </TWBS.Grid>
    );
  }
});


var Users = React.createClass({
    render: function() {
      return (
        <Viewer header     = { "Users" }
                inputData  = { inputData }
                formatData = { formatData }
                itemData   = { itemData }
                ItemView   = { UserView }
                Editor     = { this.props.activeRouteHandler }>
        </Viewer>
      );
    }
});

module.exports = Users;
