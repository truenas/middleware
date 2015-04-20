// Busy Box
// =========
// Just a Busy Spinner for Restarts and Shutdowns

"use strict";

var componentLongName = "BusyBox";

var React = require("react");

// Middleware
var MiddlewareClient = require("../middleware/MiddlewareClient");

// SessionStore stores the logged in user and the fact that login happened.
var SessionStore = require("../stores/SessionStore");

// Powerstuff
var PowerStore  = require("../stores/PowerStore");

// Middleware
var PowerMiddleware   = require("../middleware/PowerMiddleware");

// Throbber
var Throbber = require("./common/Throbber");

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
        , userText      : ""
        , passText      : ""
        , busyText      : "Busy"
        , kickin        : true
        , loggedIn      : SessionStore.getLoginStatus()
        , operation     : "Connect you to FreeNAS"
      };
    }

  , componentDidMount: function() {
      SessionStore.addChangeListener( this.handleMiddlewareChange );
      PowerStore.addChangeListener( this.handlePowerChange );
      PowerMiddleware.subscribe( componentLongName );
      this.updateBoxVisibility();
    }

  , componentWillUnmount: function () {
      PowerStore.removeChangeListener( this.handlePowerChange );
      SessionStore.removeChangeListener( this.handleMiddlewareChange );
      PowerMiddleware.unsubscribe( componentLongName );
    }

  , componentDidUpdate: function( prevProps, prevState ) {
      if ( prevState.kickin !== this.state.kickin || prevState.loggedIn !== this.state.loggedIn ) {
        this.updateBoxVisibility();
      }
    }

  , updateBoxVisibility: function () {
      if ( this.state.kickin || !this.state.loggedIn ) {
        this.showBusyBox();
      } else {
        this.hideBusyBox();
      }
    }

  , showBusyBox: function () {
      this.setState({ boxIsVisible: true });
      // clear the cached password!
      this.setState({ passText: "" });
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

  , handleMiddlewareChange: function() {
      this.setState({ loggedIn: SessionStore.getLoginStatus() });
    }

  , handlePowerChange: function() {
      var retcode = PowerStore.isEventPending();
      this.setState({
          kickin    : retcode[0]
        , operation : retcode[1]
      });
    }

  , handleUserChange: function( event ) {
      this.setState({ userText: event.target.value });
    }

  , handlePassChange: function( event ) {
      this.setState({ passText: event.target.value });
    }

  , handleKeydown: function( event ) {
      if ( event.which === 13 && this.state.userText.length ) {
        this.handleLoginClick();
      }
    }

  , handleLoginClick: function( event ) {
      // TODO: Input validation for user/pass. What are the rules?
      MiddlewareClient.login( "userpass", [this.state.userText, this.state.passText] );
    }

  , render: function () {
      var busyBody = (<div ref="Busy"  style={{ opacity: 0 }}/>);

      if ( this.state.boxIsVisible ) {
        if ( this.state.kickin ) {
          var throbberprops     = {};
          throbberprops.bsStyle = "primary";
          throbberprops.size    = 60;
          var dispMsg           = "Please wait while I " + this.state.operation;  

          busyBody = (
            <div className="overlay-dark" ref="Busy" style={{ opacity: 0 }}>
              <div className="overlay-window">
                <div>
                  <h2> {dispMsg} </h2>
                  <Throbber {...throbberprops} />
                </div>
              </div>
            </div>
          );
        } else if ( !this.state.loggedIn ) {
          busyBody = (
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
                             onClick  = { this.handleLoginClick }>{"Sign In"}</TWBS.Button>
              </div>
            </div>
          );
        }
      }

      return busyBody;
    }

});

module.exports = BusyBox;
