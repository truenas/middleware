// Busy Box
// =========
// Just a Busy Spinner for Restarts and Shutdowns

"use strict";

var React = require("react");

// Powerstuff
var PowerStore  = require("../stores/PowerStore");

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

  , consolePrint: function () {
      console.log("Suraj Power thing happened componentDidMount");
  }

  , consolePrint2: function () {
      console.log("Suraj Power thing happened componentWillUnMount");
  }

  , componentDidMount: function() {
      PowerStore.addChangeListener( this.handlePowerChange );
      PowerStore.addChangeListener( this.consolePrint );
      this.updateBoxVisibility();
    }

  , componentWillUnmount: function () {
      PowerStore.removeChangeListener( this.handlePowerChange );
      PowerStore.addChangeListener( this.consolePrint2 );
    }

  , componentDidUpdate: function( prevProps, prevState ) {
      console.log("Suraj componentDidUpdate called in BusyBox")
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

  // TODO: Fix Velocity fade-ins and outs
  // as they access the ref of "Busy" when its 
  // not yet defined. Speak with corey to figure this out
  , showBusyBox: function () {
      this.setState({ boxIsVisible: true });
      //Velocity( this.refs.Busy.getDOMNode()
      //        , "fadeIn"
      //        , { duration: this.props.animDuration } );
    }

  , hideBusyBox: function () {
      this.setState({ boxIsVisible: false });
      //Velocity( this.refs.Busy.getDOMNode()
      //        , "fadeOut"
      //        , {
      //              duration : this.props.animDuration
      //            , delay    : this.props.animDelay
      //         }
      //        );

      //this.animTimeout = setTimeout( function() {
      //    this.setState({ boxIsVisible: false });
      //  }.bind(this)
      //  , this.props.animDuration + this.props.animDelay + 250
      //);
    }

, handlePowerChange: function() {
      this.setState({ kickin: PowerStore.isEventPending() });
    }

, render: function () {
      var busySpinner = null;

      if ( this.state.boxIsVisible ) {
        busySpinner = (
          <div className="overlay-dark" ref="Busy" style={{ opacity: 0 }}>
            <div className="overlay-window">

              <div>
                <h3>{ "Please wait while I reboot(or something) (or attempt to anyways)..." || "Done." }</h3>
                <Throbber bsStyle={ this.props.throbberStyle || "primary" } />
              </div>

            </div>
          </div>
        );
      }

      return busySpinner;
    }

});

module.exports = BusyBox;
