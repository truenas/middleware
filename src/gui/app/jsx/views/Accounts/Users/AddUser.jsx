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

  , handleValueChange: function( key, event ) {
      var newEditedFields = this.state.editedFields;
      var inputValue = this.processFormInput( event );
      var dataKey = _.find(this.state.dataKeys, function (dataKey) {
        return (dataKey.key === key);
      }, this);

      // TODO: mixin? could this go in processFormInput?
      switch (dataKey.type) {
        case "string":
          newEditedFields[ key ] = inputValue;
          break;

        case "integer":
        case "number":
          newEditedFields[ key ] = _.parseInt(inputValue);
          break;

        default:
          newEditedFields[ key ] = inputValue;
          break;
      }


      this.setState( { editedFields: newEditedFields } );
    }

    // returns the next available UID after 1000 to use as a default.
  , getNextID: function() {

    }

  , receiveUsersUpdate: function() {

    }

  , submitNewUser: function() {
      var newUserValues = {};
      // Stage edited values for submission. Don't include any read-only stuff that got in somehow.
      newUserValues = this.removeReadOnlyFields(this.state.editedFields, this.state.dataKeys);
      // TODO: Only submit a user if all the required fields are there.
      UsersMiddleware.createUser( newUserValues );
  }
  , cancel: function () {

    }
  , test: function () {
    console.log("test");
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
                            value            = { this.state.editedFields["id"]? this.state.editedFields["id"]: this.props.defaultValues }
                            onChange         = {this.handleValueChange.bind( null, "id" ) }
                            groupClassName   = { _.has(this.state.editedFields, "id") && !_.isEmpty(this.state.editedFields["id"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* username */}
                <TWBS.Input type             = "text"
                            label            = "User Name"
                            value            = { this.state.editedFields["username"]? this.state.editedFields["username"]: this.props.defaultValues }
                            onChange         = {this.handleValueChange.bind( null, "username" ) }
                            groupClassName   = { _.has(this.state.editedFields, "username") && !_.isEmpty(this.state.editedFields["username"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            required />
                {/* primary group */}
                <TWBS.Input type             = "text"
                            label            = "Primary Group"
                            value            = { this.state.editedFields["group"]? this.state.editedFields["group"]: this.props.defaultValues }
                            onChange         = { this.handleValueChange.bind( null, "group" ) }
                            groupClassName   = { _.has(this.state.editedFields, "group") && !_.isEmpty(this.state.editedFields["group"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            required />
                {/* Full Name */}
                <TWBS.Input type             = "text"
                            label            = "Full Name"
                            value            = { this.state.editedFields["full_name"]? this.state.editedFields["full_name"]: this.props.defaultValues }
                            onChange         = { this.handleValueChange.bind( null, "full_name" ) }
                            groupClassName   = { _.has(this.state.editedFields, "full_name") && !_.isEmpty(this.state.editedFields["full_name"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* email */}
                <TWBS.Input type             = "text"
                            label            = "email"
                            value            = { this.state.editedFields["email"]? this.state.editedFields["email"]: this.props.defaultValues }
                            onChange         = { this.handleValueChange.bind( null, "email" ) }
                            groupClassName   = { _.has(this.state.editedFields, "email") && !_.isEmpty(this.state.editedFields["emaill"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* shell */}
                <TWBS.Input type             = "select"
                            label            = "Shell"
                            value            = { this.state.editedFields["shell"]? this.state.editedFields["shell"]: this.props.defaultValues }
                            onChange         = { this.handleValueChange.bind( null, "shell" ) }
                            groupClassName   = { _.has(this.state.editedFields, "shell") && !_.isEmpty(this.state.editedFields["shell"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8">
                            {this.generateOptionsList( this.state.shells ) }
                </TWBS.Input>
              </TWBS.Col>
              <TWBS.Col xs = {4}>
                {/* locked */}
                <TWBS.Input type             = "checkbox"
                            label            = "Locked"
                            value            = { this.state.editedFields["locked"]? this.state.editedFields["locked"]: this.props.defaultValues }
                            onChange         = {this.handleValueChange.bind( null, "locked" ) }
                            groupClassName   = { _.has(this.state.editedFields, "locked") && !_.isEmpty(this.state.editedFields["locked"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* sudo */}
                <TWBS.Input type             = "checkbox"
                            label            = "Sudo"
                            value            = { this.state.editedFields["sudo"]? this.state.editedFields["sudo"]: this.props.defaultValues }
                            onChange         = { this.handleValueChange.bind( null, "sudo" ) }
                            groupClassName   = { _.has(this.state.editedFields, "sudo") && !_.isEmpty(this.state.editedFields["sudo"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* password_disabled */}
                <TWBS.Input type             = "checkbox"
                            label            = "Password Disabled"
                            value            = { this.state.editedFields["password_disabled"]? this.state.editedFields["password_disabled"]: this.props.defaultValues }
                            onChange         = { this.handleValueChange.bind( null, "password_disabled" ) }
                            groupClassName   = { _.has(this.state.editedFields, "password_disabled") && !_.isEmpty(this.state.editedFields["password_disabled"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
              </TWBS.Col>
            </TWBS.Row>
          </TWBS.Grid>
        </form>;


      return (
        <TWBS.Grid fluid>
          { addButtons }
          { inputFields }
        </TWBS.Grid>
      );
    }
});

module.exports = AddUser;
