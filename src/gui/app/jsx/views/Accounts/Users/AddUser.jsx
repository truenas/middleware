// Add User Template
// =================
// Handles the process of adding a new user. Provides an interface for setting up
// the configurable attributes of a new user.

"use strict";

var _      = require("lodash");
var React  = require("react");
var TWBS   = require("react-bootstrap");

var UsersMiddleware = require("../../../middleware/UsersMiddleware");

var GroupsStore      = require("../../../stores/GroupsStore");

var inputHelpers = require("../../../components/mixins/inputHelpers");
var userMixins   = require("../../../components/mixins/userMixins");


var AddUser = React.createClass({

    mixins: [   inputHelpers
              , userMixins ]

  , contextTypes: {
      router: React.PropTypes.func
  }

  , propTypes: {
        viewData: React.PropTypes.object.isRequired
    }

  , getInitialState: function() {
      var defaultValues = {
                              id                : this.getNextUID()
                            , shell             : "/bin/csh"
                          };

      return {
          editedFields  : {}
        , defaultValues : defaultValues
        , dataKeys      : this.props.viewData.format.dataKeys
      };
    }

  , handleValueChange: function( key, event ) {
      var newEditedFields = this.state.editedFields;

      var dataKey = _.find(this.state.dataKeys, function (dataKey) {
        return (dataKey.key === key);
      }, this);

      newEditedFields[ key ] = this.processFormInput( event, dataKey );

      this.setState( { editedFields: newEditedFields } );
    }

    // Will return the next recommended UID (to be used as a default).
  , getNextUID: function() {

    }

  , submitNewUser: function() {
      var routing = this.props.viewData.routing;
      var newUserValues = {};
      var params        = {};

      // Stage edited values for submission. Don't include any read-only stuff that got in somehow.
      newUserValues = this.removeReadOnlyFields( this.state.editedFields, this.state.dataKeys );

      // Get ready to send the view to the new user.
      params[ routing[ "param" ] ] = newUserValues[ "username" ];

      // Submits the user and moves the view to the new user.
      // TODO: Only submit a user if all the required fields are there.
      // TODO: Make sure the new user was actually created before transitioning the route.
      UsersMiddleware.createUser( newUserValues, this.context.router.transitionTo( routing[ "route" ], params) );
  }

  , cancel: function () {

    }

  , render: function() {

      var addButtons =
        <TWBS.ButtonToolbar>
          <TWBS.Button className = "pull-right"
                       onclick   = { this.cancel }
                       bsStyle   = "default">{"Cancel"}</TWBS.Button>
          <TWBS.Button className = "pull-right"
                       disabled  = { _.isEmpty( this.state.editedFields ) }
                       onClick   = { this.submitNewUser}
                       bsStyle   = "info">{"Save New User"}</TWBS.Button>
        </TWBS.ButtonToolbar>;

      var inputFields =
        <form className = "form-horizontal">
          <TWBS.Grid fluid>
            {/*TODO: Style unedited default values differently from edited ones*/}
            <TWBS.Row>
              <TWBS.Col xs = {8}>
                {/* User id */}
                <TWBS.Input type             = "text"
                            label            = "User ID"
                            value            = { this.state.editedFields["id"]? this.state.editedFields["id"]: this.state.defaultValues["id"] }
                            onChange         = { this.handleValueChange.bind( null, "id" ) }
                            groupClassName   = { _.has(this.state.editedFields, "id") && !_.isEmpty(this.state.editedFields["id"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* username */}
                <TWBS.Input type             = "text"
                            label            = "User Name"
                            value            = { this.state.editedFields["username"]? this.state.editedFields["username"]: null }
                            onChange         = { this.handleValueChange.bind( null, "username" ) }
                            groupClassName   = { _.has(this.state.editedFields, "username") && !_.isEmpty(this.state.editedFields["username"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            required />
                {/* Full Name */}
                <TWBS.Input type             = "text"
                            label            = "Full Name"
                            value            = { this.state.editedFields["full_name"]? this.state.editedFields["full_name"]: null }
                            onChange         = { this.handleValueChange.bind( null, "full_name" ) }
                            groupClassName   = { _.has(this.state.editedFields, "full_name") && !_.isEmpty(this.state.editedFields["full_name"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* email */}
                <TWBS.Input type             = "text"
                            label            = "email"
                            value            = { this.state.editedFields["email"]? this.state.editedFields["email"]: null }
                            onChange         = { this.handleValueChange.bind( null, "email" ) }
                            groupClassName   = { _.has(this.state.editedFields, "email") && !_.isEmpty(this.state.editedFields["email"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* shell */}
                <TWBS.Input type             = "select"
                            label            = "Shell"
                            value            = { this.state.editedFields["shell"]? this.state.editedFields["shell"]: this.state.defaultValues["shell"] }
                            onChange         = { this.handleValueChange.bind( null, "shell" ) }
                            groupClassName   = { _.has(this.state.editedFields, "shell") && !_.isEmpty(this.state.editedFields["shell"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" >
                            { this.generateOptionsList( this.state.shells, "name" ) }
                </TWBS.Input>
                {/* primary group */}
                {/* TODO: Recommend the default group based on the username. Requires creating a group at user-creation time.*/}
                <TWBS.Input type             = "select"
                            label            = "Primary Group"
                            value            = { this.state.editedFields["group"]? this.state.editedFields["group"]: null }
                            onChange         = { this.handleValueChange.bind( null, "group" ) }
                            groupClassName   = { _.has(this.state.editedFields, "group") && !_.isEmpty(this.state.editedFields["group"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            required >
                            { this.generateOptionsList( GroupsStore.getAllGroups(), "id", "name" ) }
                </TWBS.Input>
                {/* sshpubkey */}
                <TWBS.Input type             = "textarea"
                            label            = "Public Key"
                            value            = { this.state.editedFields["sshpubkey"]? this.state.editedFields["sshpubkey"]: null }
                            onChange         = { this.handleValueChange.bind( null, "sshpubkey" ) }
                            groupClassName   = { _.has(this.state.editedFields, "sshpubkey") && !_.isEmpty(this.state.editedFields["sshpubkey"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            rows             = "10" />
              </TWBS.Col>
              <TWBS.Col xs = {4}>
                {/* locked */}
                <TWBS.Input type             = "checkbox"
                            label            = "Locked"
                            value            = { this.state.editedFields["locked"] }
                            onChange         = { this.handleValueChange.bind( null, "locked" ) }
                            groupClassName   = { _.has(this.state.editedFields, "locked") && !_.isEmpty(this.state.editedFields["locked"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* sudo */}
                <TWBS.Input type             = "checkbox"
                            label            = "Sudo"
                            value            = { this.state.editedFields["sudo"] }
                            onChange         = { this.handleValueChange.bind( null, "sudo" ) }
                            groupClassName   = { _.has(this.state.editedFields, "sudo") && !_.isEmpty(this.state.editedFields["sudo"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* password_disabled */}
                <TWBS.Input type             = "checkbox"
                            label            = "Password Disabled"
                            value            = { this.state.editedFields["password_disabled"] }
                            onChange         = { this.handleValueChange.bind( null, "password_disabled" ) }
                            groupClassName   = { _.has(this.state.editedFields, "password_disabled") && !_.isEmpty(this.state.editedFields["password_disabled"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
              </TWBS.Col>
            </TWBS.Row>
          </TWBS.Grid>
        </form>;


      return (
        <div className="viewer-item-info">
          <TWBS.Grid fluid>
            { addButtons }
            { inputFields }
          </TWBS.Grid>
        </div>
      );
    }
});

module.exports = AddUser;
