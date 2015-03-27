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
        {/* editButton */}

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
          {/* editButton */}

        </TWBS.Grid>
      );
  }
});

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

        switch( this.state.currentMode ) {
          default:
          case "view":
            DisplayComponent = GroupView;
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
