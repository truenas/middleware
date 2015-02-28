/** @jsx React.DOM */

"use strict";

var React = require("react");

var Router = require("react-router");
var Link   = Router.Link;

var TWBS   = require("react-bootstrap");
var Icon   = require("./Icon");

// Path definitions
// TODO: Convert to Flux or other external file
var paths = [
  {
      path    : "dashboard"
    , icon    : "dashboard"
    , label   : "Dashboard"
    , status  : "danger"
  },{
      path    : "accounts"
    , icon    : "paper-plane"
    , label   : "Accounts"
    , status  : null
  },{
      path    : "tasks"
    , icon    : "paw"
    , label   : "Tasks"
    , status  : null
  },{
      path    : "networks"
    , icon    : "moon-o"
    , label   : "Networks"
    , status  : null
  },{
      path    : "storage"
    , icon    : "magic"
    , label   : "Storage"
    , status  : null
  },{
      path    : "sharing"
    , icon    : "cut"
    , label   : "Sharing"
    , status  : null
  },{
      path    : "services"
    , icon    : "bitcoin"
    , label   : "Services"
    , status  : null
  },{
      path    : "system-tools"
    , icon    : "ambulance"
    , label   : "System Tools"
    , status  : "warning"
  },{
      path    : "control-panel"
    , icon    : "paragraph"
    , label   : "Control Panel"
    , status  : null
  },{
      path    : "power"
    , icon    : "plug"
    , label   : "Power"
    , status  : null
  }
];
var menuTiming = 600;
var debugUrl = "";

if ( typeof window !== "undefined" ) {
    debugUrl = window.location.protocol + "//" + document.domain + ":8180/rpc";
}

var PrimaryNavigation = React.createClass({

    getInitialState: function() {
      return { expanded: true };
    }

  , componentDidMount: function () {
      // After the component has a real DOM representation, store the auto width
      // value of the navbar
      this.setState({
        fullNavWidth: this.refs.navRoot.getDOMNode().offsetWidth + "px"
      });
    }

  , handleMenuToggle: function( event ) {
      event.stopPropagation();

      if ( this.state.expanded ) {
        this.collapseMenu();
      } else {
        this.expandMenu();
      }
    }

  , expandMenu: function () {
      var expandSequence = [
        {   elements   : this.refs.navRoot.getDOMNode()
          , properties : { width: this.state.fullNavWidth }
          , options    : {
                duration : menuTiming
              , easing   : "easeInOutBounce"
            }
        },{
            elements      : document.getElementsByClassName("nav-item-label")
          , properties    : "fadeIn"
          , options: {
                duration      : menuTiming
              , sequenceQueue : false
              , complete      : this.setState({ expanded: true })
            }
        }
      ];

      Velocity.RunSequence( expandSequence );
    }

  , collapseMenu: function () {
      var expandSequence = [
        {   elements   : this.refs.navRoot.getDOMNode()
          , properties : { width: "60px" }
          , options    : {
                duration : menuTiming
              , easing   : "easeInOutBounce"
            }
        },{
            elements      : document.getElementsByClassName("nav-item-label")
          , properties    : "fadeOut"
          , options: {
                duration      : menuTiming
              , sequenceQueue : false
              , complete      : this.setState({ expanded: false })
            }
        }
      ];

      Velocity.RunSequence( expandSequence );
    }

  , render: function() {
      var createNavItem = function ( rawItem, index ) {
        return (
          <li role      = "presentation"
              className = "nav-item"
              key       = { index } >
            <Link to = { rawItem.path }>
              <Icon glyph        = { rawItem.icon }
                    badgeContent = { rawItem.status ? "!" : "" /* TODO: Better content, from Flux store */ }
                    badgeStyle   = { rawItem.status } />
              <span className = "nav-item-label" >{ rawItem.label }</span>
            </Link>
          </li>
        );
      };

      // TODO: Revert changes made for #7908 once externally resolved.
      return (
        <TWBS.Nav stacked
                  ref       = "navRoot"
                  className = "primary-nav">
          <div className= "primary-nav-label-toggle"
               onClick  = { this.handleMenuToggle }>
            {"…"}
          </div>

          { paths.map( createNavItem ) }

          <li role      = "presentation"
              className = "nav-item">
              <a href = { debugUrl }>
                  <Icon glyph      = ""
                      badgeContent = ""
                      badgeStyle   = { null } />
                  <span className = "nav-item-label" >Debug</span>
              </a>
          </li>

        </TWBS.Nav>
      );
    }

});

module.exports = PrimaryNavigation;
