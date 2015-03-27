// Group Item Template
// ==================
// Handles the viewing and editing of individual group items. Shows a non-editable
// overview of the group, and mode-switches to a more standard editor panel. 
// Group is set by providing a route parameter.

"use strict";

var _      = require("lodash");
var React  = require("react");
var TWBS   = require("react-bootstrap");
var Router = require("react-router");

var viewerUtil = require("../../../components/Viewer/viewerUtil");
var editorUtil  = require("../../../components/Viewer/Editor/editorUtil");
var activeRoute = require("../../../components/Viewer/mixins/activeRoute");

var GroupsMiddleware = require("../../../middleware/GroupsMiddleware");
var GroupsStore      = require("../../../stores/GroupsStore");

var UsersMiddleware = require("../../../middleware/UsersMiddleware");
var UsersStore      = require("../../../stores/UsersStore");

var GroupView = React.createClass({

    propTypes: {
      item: React.PropTypes.object.isRequired
    }

  , getMembers: function( groupid ) {
    if ( UsersStore.getUsersByGroup( groupid )[0] ) {
      return UsersStore.getUsersByGroup( groupid )[0].username;
    } else {
      return "";
    }
  }

  , render: function() {
      var builtInGroupAlert = null;
      var editButton = null;

      if ( this.props.item["builtin"] ) {
        builtInGroupAlert = (
          <TWBS.Alert bsStyle   = "info"
                      className = "text-center">
            <b>{"This is a built-in FreeNAS group account."}</b>
          </TWBS.Alert>
        );
      }

      editButton = (
        <TWBS.Row>
          <TWBS.Col xs={12}>
            <TWBS.Button className = "pull-right"
                         onClick   = { this.props.handleViewChange.bind(null, "edit") }
                         bsStyle   = "info" >{"Edit Group"}</TWBS.Button>
          </TWBS.Col>
        </TWBS.Row>
      );

      return (
        <TWBS.Grid fluid>
        {/* "Edit Group" Button - Top */}
        { editButton }

        <TWBS.Row>
          <TWBS.Col xs={3}
                    className="text-center">
            <viewerUtil.ItemIcon primaryString  = { this.props.item["name"] }
                                 fallbackString = { this.props.item["id"] }
                                 seedNumber     = { this.props.item["id"] } /> 
          </TWBS.Col>
          <TWBS.Col xs={9}>
            <h3>{ this.props.item["name"] }</h3>
            <hr />
          </TWBS.Col>
        </TWBS.Row>

          {/* Shows a warning if the group account is built in */}
          { builtInGroupAlert }

          {/* Primary group data overview */}

        <TWBS.Row>
          <viewerUtil.DataCell title  = { "Group ID" }
                               colNum = { 3 }
                               entry  = { this.props.item["id"] }/>
          <viewerUtil.DataCell title = { "Users" }
                               colNum = { 9 }
                               entry = { this.getMembers( this.props.item["id"] ) } />
        </TWBS.Row>

          {/* "Edit Group" Button - Bottom */}
          { editButton }

        </TWBS.Grid>
      );
  }
});

// EDITOR PANE
var GroupEdit = React.createClass({

    propTypes: {
      item: React.PropTypes.object.isRequired
    }

  , getInitialState: function() {
      return {
          modifiedValues : {}
        , mixedValues    : this.props.item
      }
  }

  , componentWillRecieveProps: function( nextProps ) {
      var newModified = {};
      var oldModified = _.cloneDeep( this.state.modifiedValues );

      // Any remote changes will cause the current property to be shown as
      // having been "modified", signalling to the user that saving it will
      // have the effect of changing that value
      _.forEach( nextProps.item, function( value, key ) {
        if ( this.props.item[ key ] !== value ) {
          newModified[ key ] = this.props.item[ key ];
        }
      }.bind(this) );

      // Any remote changes which are the same as locally modified changes should
      // cause the local modifications to be ignored.
      _.forEach( oldModified, function( value, key ) {
        if ( this.props.item[ key ] === value ) {
          delete oldModified[ key ];
        }
      }.bind(this) );

      this.setState({
          modifiedValues : _.assign( oldModified, newModified )
      });
    }

  , handleValueChange: function( key, event ) {
      var newValues  = this.state.modifiedValues;
      var inputValue;
      if (event.target.type === "checkbox") {
        inputValue = event.target.checked;
      } else {
        inputValue = event.target.value;
      }
      // We don't want to submit non-changed data to the middleware, and it's
      // easy for data to appear "changed", even if it's the same. Here, we
      // check to make sure that the input value we've just receieved isn't the
      // same as what the last payload from the middleware shows as the value
      // for the same key. If it is, we `delete` the key from our temp object
      // and update state.
      if ( this.props.item[ key ] === inputValue ) {
        delete newValues[ key ];
      } else {
        newValues[ key ] = inputValue;
      }

      // mixedValues functions as a clone of the original item passed down in
      // props, and is modified with the values that have been changed by the
      // user. This allows the display components to have access to the
      // "canonically" correct item, merged with the un-changed values.
      this.setState({
          modifiedValues : newValues
        , mixedValues    : _.assign( _.cloneDeep( this.props.item ), newValues )
      });
    }

  , submitGroupUpdate: function() {
      GroupsMiddleware.updateGroup( this.props.item["id"], this.state.modifiedValues );
    }

  , render: function() {
      var builtInGroupAlert = null;
      var editButtons       = null;

      if ( this.props.item["builtin"] ) {
        builtInGroupAlert = (
          <TWBS.Alert bsStyle   = "warning"
                      className = "text-center">
            <b>{"You should only edit a system group if you know exactly what you are doing."}</b>
          </TWBS.Alert>
        );
      }

      editButtons =
        <TWBS.ButtonToolbar>
            <TWBS.Button className = "pull-right"
                         onClick   = { this.props.handleViewChange.bind(null, "view") }
                         bsStyle   = "default" >{"Cancel"}</TWBS.Button>
            <TWBS.Button className = "pull-right"
                         disabled  = { _.isEmpty( this.state.modifiedValues ) ? true : false }
                         onClick   = { this.submitGroupUpdate }
                         bsStyle   = "info" >{"Save Changes"}</TWBS.Button>
        </TWBS.ButtonToolbar>;

      return (
        <TWBS.Grid fluid>
          {/* Save and Cancel Buttons - Top */}
          { editButtons }

          {/* Shows a warning if the group is built in */}
          { builtInGroupAlert }

          <form className="form-horizontal">
            {
              this.props["dataKeys"].map( function( displayKeys, index ) {
                return editorUtil.identifyAndCreateFormElement(
                          // value
                          this.state.mixedValues[ displayKeys["key"] ]
                          // displayKeys
                        , displayKeys
                          //changeHandler
                        , this.handleValueChange
                          // key
                        , index
                          // wasModified
                        , _.has( this.state.modifiedValues, displayKeys["key"] )
                      );
              }.bind( this ) ) 
            }
          </form>

          {/* Save and Cancel Buttons - Bottom */}
          { editButtons }
        </TWBS.Grid>
      );
    }
});


// CONTROLLER-VIEW
var GroupItem = React.createClass({

      propTypes: {
        viewData : React.PropTypes.object.isRequired
      }

    , mixins: [ Router.State, activeRoute ]

    , getInitialState: function() {
        return {
            targetGroup : this.getGroupFromStore()
          , currentMode : "view"
          , activeRoute : this.getActiveRoute()
        };
      }

    , componentDidUpdate: function( prevProps, prevState ) {
        var activeRoute = this.getActiveRoute();

        if ( activeRoute !== prevState.activeRoute ) {
          this.setState({
              targetGroup  : this.getGroupFromStore()
            , currentMode : "view"
            , activeRoute : activeRoute
          });
        }
      }

    , componentDidMount: function() {
        GroupsStore.addChangeListener( this.updateGroupInState );
      }

    , componentWillUnmount: function() {
        GroupsStore.removeChangeListener( this.updateGroupInState );
      }

    , getGroupFromStore: function() {
        return GroupsStore.findGroupByKeyValue( this.props.viewData.format["selectionKey"], this.getActiveRoute() );
      }

    , updateGroupInState: function() {
        this.setState({ targetGroup: this.getGroupFromStore() });
      }

    , handleViewChange: function( nextMode, event ) {
        this.setState({ currentMode: nextMode });
      }

    , render: function() {
        var DisplayComponent = null;
        var processingText = "";

        // PROCESSING OVERLAY
        if ( GroupsStore.isLocalTaskPending( this.state.targetGroup["id"] ) ) {
          processingText = "Saving changes to '" + this.state.targetGroup[ this.props.viewData.format["primaryKey" ] ] + "'";
        } else if (GroupsStore.isGroupUpdatePending( this.state.targetGroup[ "id"] ) ) {
          processingText = "Group '" + this.state.targetGroup[ this.props.viewData.format["primaryKey"] ] + "' was updated remotely.";
        }

        // DISPLAY COMPONENT
        switch( this.state.currentMode ) {
          default:
          case "view":
            DisplayComponent = GroupView;
            break;
          case "edit":
            DisplayComponent = GroupEdit;
            break;
        }

        return (
          <div className="viewer-item-info">

            {/* Overlay to block interaction while tasks or updates are processing */}
            <editorUtil.updateOverlay updateString={ processingText } />
            <DisplayComponent handleViewChange = { this.handleViewChange }
                              item             = { this.state.targetGroup }
                              dataKeys         = { this.props.viewData.format["dataKeys"] } />

          </div>
        );
      }
});

module.exports = GroupItem;
