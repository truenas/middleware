// Busy Box
// =========
// Just a Busy Spinner for Restarts and Shutdowns

"use strict";

var React = require("react");

// Powerstuff
var PowerStore  = require("../stores/PowerStore");

// PowerMiddleware
var PowerMiddleware = require("../middleware/PowerMiddleware")

// Throbber
var Throbber = require("./common/Throbber");


var BusyBox = React.createClass({

    propTypes: {
        animDuration : React.PropTypes.number
      , animDelay    : React.PropTypes.number
    }

  , getDefaultProps: function() {
      return {
          animDuration : 500
        , animDelay    : 0
      };
    }

  , getInitialState: function() {
      return {
          boxIsVisible  : false
        , busyText      : "Busy"
        , kickin        : false
      };
    }

  , componentDidMount: function() {
      PowerStore.addChangeListener( this.handlePowerChange );
      PowerMiddleware.subscribe();
      this.updateBoxVisibility();
    }

  , componentWillUnmount: function () {
      PowerStore.removeChangeListener( this.handlePowerChange );
      PowerMiddleware.unsubscribe();
    }

  , componentDidUpdate: function( prevProps, prevState ) {
      if ( prevState.kickin !== this.state.kickin ) {
        this.updateBoxVisibility();
      }
    }

  , updateBoxVisibility: function () {
      if ( this.state.kickin ) {
        this.showBusyBox();
      } else {
        this.hideBusyBox();
      }
    }

  , showBusyBox: function () {
      this.setState({ boxIsVisible: true });
      Velocity( this.refs.Busy.getDOMNode()
             , "fadeIn"
             , { duration: this.props.animDuration } );
    }

  , hideBusyBox: function () {
      this.setState({ boxIsVisible: false });
      Velocity( this.refs.Busy.getDOMNode()
             , "fadeOut"
             , {
                   duration : this.props.animDuration
                 , delay    : this.props.animDelay
              }
             );

      this.animTimeout = setTimeout( function() {
         this.setState({ boxIsVisible: false });
       }.bind(this)
       , this.props.animDuration + this.props.animDelay + 250
      );
    }

, handlePowerChange: function() {
      this.setState({ kickin: PowerStore.isEventPending() });
    }

, render: function () {
      var busySpinner = (<div ref="Busy"  style={{ opacity: 0 }}/>);

      if ( this.state.boxIsVisible ) {

        var throbberprops = {};
        throbberprops.bsStyle = "primary";
        throbberprops.size  = 60;
        busySpinner = (
          <div className="overlay-dark" ref="Busy" style={{ opacity: 0 }}>
            <div className="overlay-window">
              <div>
                <h3>{ "Please wait while I Reboot/Shutdown/Update (or something....rather attempt to anyways)..."  }</h3>
                <Throbber {...throbberprops} />
              </div>

            </div>
          </div>
        );
      }

      return busySpinner;
    }

});

module.exports = BusyBox;
