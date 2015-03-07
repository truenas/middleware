// Busy Box
// =========
// Just a Busy Spinner for Restarts and Shutdowns

"use strict";

var React = require("react");

// Powerstuff
var PowerStore  = require("../stores/PowerStore");

// Twitter Bootstrap React components
var TWBS = require("react-bootstrap");


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
      };
    }

  , componentDidMount: function() {
      PowerStore.addChangeListener( this.handleMiddlewareChange );
      this.updateBoxVisibility();
    }

  , componentWillUnmount: function () {
      PowerStore.removeChangeListener( this.handleMiddlewareChange );
    }

  , componentDidUpdate: function( prevProps, prevState ) {
      if ( prevState.authenticated !== this.state.authenticated ) {
        this.updateBoxVisibility();
      }
    }

  , updateBoxVisibility: function () {
      if ( this.state.authenticated ) {
        this.hideBusyBox();
      } else {
        this.showBusyBox();
      }
    }

  , showBusyBox: function () {
      this.setState({ boxIsVisible: true });
      Velocity( this.refs.Busy.getDOMNode()
              , "fadeIn"
              , { duration: this.props.animDuration } );
    }

  , hideBUSYBox: function () {
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

  , render: function () {
      var busySpinner = null;

      if ( this.state.boxIsVisible ) {
        busySpinner = (
          <div className="overlay-dark" ref="Busy" style={{ opacity: 0 }}>
            <div className="overlay-window">

              <h3>{"Welcome to FreeNAS 10"}</h3>
              <hr />

              <div className="form-group">
                <input className   = "form-control"
                       type        = "text"
                       value       = { this.state.userText }
                       onChange    = { this.handleUserChange }
                       onKeyDown   = { this.handleKeydown }
                       placeholder = "Username" />
              </div>
              <div className="form-group">
                <input className   = "form-control"
                       type        = "password"
                       value       = { this.state.passText }
                       onChange    = { this.handlePassChange }
                       onKeyDown   = { this.handleKeydown }
                       placeholder = "Password" />
              </div>

              <TWBS.Button block bsStyle="info"
                           disabled = { this.state.userText.length ? false : true }
                           onClick  = { this.handleBusyClick }>{"Sign In"}</TWBS.Button>
            </div>
          </div>
        );
      }

      return busySpinner;
    }

});

module.exports = BusyBox;
