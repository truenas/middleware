// Add Group Template
// ==================
// Handles the process of adding a new group.

"use strict";

var _      = require("lodash");
var React  = require("react");
var TWBS   = require("react-bootstrap");

var GroupsMiddleware = require("../../../middleware/GroupsMiddleware");

var inputHelpers = require("../../../components/mixins/inputHelpers");

var AddGroup = React.createClass({

    mixins: [ inputHelpers ]

  , contextTypes: {
      router: React.PropTypes.func
    }

  , propTypes: {
      viewData: React.PropTypes.object.isRequired
    }

  , getInitialState: function() {
      return {
          editedFields : {}
        , dataKeys     : this.props.viewData.format.dataKeys
        , nextGID      : this.getNextGID()
      };
    }

  , handleValueChange: function( key, event ) {
      var newEditedFields = this.state.editedFields;

      var dataKey = _.find(this.state.dataKeys, function( dataKey ) {
        return (dataKey.key === key);
      });

      newEditedFields[ key ] = this.processFormInput( event, dataKey );

      this.setState( { editedFields: newEditedFields } );
    }

    // Will return the next recommended GID (to be used as a default).
  , getNextGID: function() {

    }

  , submitNewGroup: function() {
      var routing = this.props.viewData.routing;
      var newGroupValues = {};
      var params         = {};

      // Stage values for submission. Read-only values are not allowed.
      newGroupValues = this.removeReadOnlyFields( this.state.editedFields, this.state.dataKeys );

      // Set up to forward the view to the created group.
      params[ routing[ "param" ] ] = newGroupValues[ "name" ];

      // Submit the new group and redirect the view to it.
      // TODO: Does this need additional input validation?
      // TODO: Only redirect if the group was actually created.
      GroupsMiddleware.createGroup( newGroupValues, this.context.router.transitionTo( routing[ "route" ], params) );

    }

    // TODO: There is probably room to genericize this into a mixin.
  , cancel: function () {
      this.context.router.transitionTo( "groups" );
    }

  , render: function() {
      var addButtons =
        <TWBS.ButtonToolbar>
          <TWBS.Button className = "pull-right"
                       onClick   = { this.cancel }
                       bsStyle   = "default">{"Cancel"}</TWBS.Button>
          <TWBS.Button className = "pull-right"
                       disabled  = { _.isEmpty( this.state.editedFields ) }
                       onClick   = { this.submitNewGroup}
                       bsStyle   = "info">{"Save New Group"}</TWBS.Button>
        </TWBS.ButtonToolbar>;

      var inputFields =
        <form className = "form-horizontal">
          <TWBS.Grid fluid>
            <TWBS.Row>
              <TWBS.Col xs = {4}>
                {/* Group id */}
                <TWBS.Input type             = "text"
                            label            = "Group ID"
                            value            = { this.state.editedFields["id"]? this.state.editedFields["id"]: this.state.nextGID }
                            onChange         = { this.handleValueChange.bind( null, "id" ) }
                            groupClassName   = { _.has(this.state.editedFields, "id") && !_.isEmpty(this.state.editedFields["id"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
              </TWBS.Col>
              <TWBS.Col xs = {8}>
                {/* username */}
                <TWBS.Input type             = "text"
                            label            = "Group Name"
                            value            = { this.state.editedFields["name"]? this.state.editedFields["name"]: null }
                            onChange         = { this.handleValueChange.bind( null, "name" ) }
                            groupClassName   = { _.has(this.state.editedFields, "name") && !_.isEmpty(this.state.editedFields["name"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            required />
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

module.exports = AddGroup;
