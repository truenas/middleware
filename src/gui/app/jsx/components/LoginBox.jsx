// Login Box
// =========
// Authentication window for FreeNAS. Displayed whenever the middleware is in a logged out state.

"use strict";

var React = require("react");

// Middleware
var MiddlewareClient = require("../middleware/MiddlewareClient");

// SessionStore stores the logged in user and the fact that login happened.
var SessionStore = require("../stores/SessionStore");

// Twitter Bootstrap React components
var TWBS = require("react-bootstrap");


var LoginBox = React.createClass({

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
          userText      : ""
        , passText      : ""
        , boxIsVisible  : false
        , loggedIn      : SessionStore.getLoginStatus()
      };
    }

  , componentDidMount: function() {
      SessionStore.addChangeListener( this.handleMiddlewareChange );
      this.updateBoxVisibility();
    }

  , componentWillUnmount: function () {
      SessionStore.removeChangeListener( this.handleMiddlewareChange );
    }

  , componentDidUpdate: function( prevProps, prevState ) {

      if ( prevState.loggedIn !== this.state.loggedIn ) {
        this.updateBoxVisibility();
      }
    }

  , updateBoxVisibility: function () {
      if ( this.state.loggedIn) {
        this.hideLoginBox();
      } else {
        this.showLoginBox();
      }
    }

  , showLoginBox: function () {
      this.setState({ boxIsVisible: true });
      Velocity( this.refs.login.getDOMNode()
              , "fadeIn"
              , { duration: this.props.animDuration } );
    }

  , hideLoginBox: function () {
      Velocity( this.refs.login.getDOMNode()
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

  , handleUserChange: function( event ) {
      this.setState({ userText: event.target.value });
    }

  , handlePassChange: function( event ) {
      this.setState({ passText: event.target.value });
    }

  , handleMiddlewareChange: function() {
      this.setState({ loggedIn: SessionStore.getLoginStatus() });
    }

  , handleKeydown: function( event ) {
      if ( event.which === 13 && this.state.userText.length ) {
        this.handleLoginClick();
      }
    }

  , handleLoginClick: function( event ) {

      // TODO: Input validation for user/pass. What are the rules?

      MiddlewareClient.login( this.state.userText, this.state.passText );
    }

  , render: function () {
      var loginWindow = null;

      if ( this.state.boxIsVisible ) {
        loginWindow = (
          <div className="overlay-dark" ref="login" style={{ opacity: 0 }}>
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

      return loginWindow;
    }

});

module.exports = LoginBox;
