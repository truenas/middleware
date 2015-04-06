"use strict";

var _           = require("lodash");
var React       = require("react");
var Router      = require("react-router");
var activeRoute = require("../mixins/activeRoute");

var Editor = React.createClass({

    propTypes: {
        viewData  : React.PropTypes.object.isRequired
      , inputData : React.PropTypes.any.isRequired
      , ItemView  : React.PropTypes.any.isRequired // FIXME: React 0.12 has better propTypes
      , EditView  : React.PropTypes.any            // FIXME: React 0.12 has better propTypes
    }

  , mixins: [ Router.State, activeRoute ]

  , getInitialState: function() {
      return {
          targetItem  : this.changeTargetItem( this.props.inputData )
        , currentMode : "view"
      };
    }

  , componentWillReceiveProps: function( nextProps ) {
      // TODO: Optimize based on changing props. Might need a shouldComponentUpdate.
      var nextTargetItem = this.changeTargetItem( nextProps.inputData );

      this.setState({
          targetItem  : nextTargetItem
        , currentMode : ( nextTargetItem[ this.props.viewData.format["selectionKey"] ] !== this.state.targetItem[ this.props.viewData.format["selectionKey"] ] ? "view" : this.state.currentMode )
      });
    }

  , changeTargetItem: function( inputData ) {
      return _.find( inputData, function( item ) {
          // Returns the first object from the input array whose selectionKey matches
          // the current route's dynamic portion. For instance, /accounts/users/root
          // with bsdusr_usrname as the selectionKey would match the first object
          // in inputData whose username === "root"

          return this.getActiveRoute() === item[ this.props.viewData.format["selectionKey"] ];

        }.bind(this)
      );
    }

  , handleViewChange: function ( nextMode, event ) {
      this.setState({ currentMode: nextMode });
    }

  , render: function() {
      var DisplayComponent;

      switch ( this.state.currentMode ) {

        default:
        case "view":
          DisplayComponent = this.props.ItemView;
          break;

        case "edit":
          DisplayComponent = this.props.EditView;
          break;

      }

      return (
        <DisplayComponent handleViewChange = { this.handleViewChange }
                          item             = { this.state.targetItem }
                          formatData       = { this.props.viewData.format } />
      );
    }

});

module.exports = Editor;
