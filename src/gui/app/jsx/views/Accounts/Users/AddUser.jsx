// Add User Template
// =================
// Handles the process of adding a new user. Provides an interface for setting up
// the configurable attributes of a new user.

"use strict";

var _      = require("lodash");
var React  = require("react");
var TWBS   = require("react-bootstrap");

    // Will be used to submit changes. Remove comment when done.
var UsersMiddleware = require("../../../middleware/UsersMiddleware");
var UsersStore      = require("../../../stores/UsersStore");

var GroupsStore      = require("../../../stores/GroupsStore");

var inputHelpers = require("../../../components/mixins/inputHelpers");
var userMixins   = require("../../../components/mixins/userMixins");


var AddUser = React.createClass({

    mixins: [   inputHelpers
              , userMixins ]

  , propTypes: {
        viewData: React.PropTypes.object.isRequired
    }

  , getInitialState: function() {
      var defaultValues = {
                              id                : this.getNextID()
                            , shell             : "/bin/csh"
                            , locked            : false
                            , sudo              : false
                            , password_disabled : false
                          };

      return {
          groups        : this.getGroups()
        , editedFields  : {}
        , defaultValues : defaultValues
        , dataKeys      : this.props.viewData.format.dataKeys
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
