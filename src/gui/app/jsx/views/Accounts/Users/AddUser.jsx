// Add User Template
// =================
// Handles the process of adding a new user. Provides an interface for setting up
// the configurable attributes of a new user.

"use strict";

var _      = require("lodash");
var React  = require("react");
var TWBS   = require("react-bootstrap");
var Router = require("react-router");

    // Will be used to submit changes. Remove comment when done.
var UsersMiddleware = require("../../../middleware/UsersMiddleware");
var UsersStore      = require("../../../stores/UsersStore");

    // Will be user to get a list of groups to which the user may be added.
var GroupsMiddleware = require("../../../middleware/GroupsMiddleware");
var GroupsStore      = require("../../../stores/GroupsStore");

var AddUser = React.createClass({

    propTypes: {
      userPrototype: React.PropTypes.object.isRequired
    }

  , getInitialState: function() {
    return {
        groups       : this.getGroups()
      , editedFields : {}
    };
  }

  , componentDidMount: function() {
      UsersStore.addChangeListener( this.receiveUsersUpdate );
    }

  , componentWillUnmount: function() {
      UsersStore.removeChangeListener( this.receiveUsersUpdate);
  }

  , getGroups: function() {
      return GroupsStore.getAllGroups();
    }

  , receiveUsersUpdate: function() {

  }

  , render: function() {

      return (
        <TWBS.Grid fluid>
          <TWBS.Row>
            <TWBS.Col>
            </TWBS.Col>
          </TWBS.Row>
        </TWBS.Grid>
      );
    }
});

module.exports = AddUser;
