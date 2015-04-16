// TOGGLE SWITCH
// =============
// A simple boolean toggle switch that performs the same functionality as a
// checkbox.

"use strict";

var React = require("react");

var ToggleSwitch = React.createClass({
    propTypes: {
        isToggled : React.PropTypes.bool
      , onChange  : React.PropTypes.func
    }

  , getDefaultProps: function() {
      return {
          isToggled : false
        , onChange  : function( toggleState, reactID ) {
                        console.warn("No onChange handler was provided for ToggleSwitch", reactID );
                      }
      };
    }

  , getInitialState: function() {
      return {
          toggled: this.props.isToggled
      };
    }

  , handleToggleClick: function( event, reactID ) {
      event.stopPropagation();
      event.preventDefault();

      var newToggleState = !this.state.toggled;

      this.setState({ toggled: newToggleState });

      this.props.onChange( newToggleState, reactID );
    }

  , render: function() {
      var toggleClasses = ["toggle-switch"];

      if ( this.state.toggled ) {
        toggleClasses.push("on");
      }

      return (
        <div
          className = { toggleClasses.join(" ") }
          onClick   = { this.handleToggleClick } />
      );
    }

});

module.exports = ToggleSwitch;
