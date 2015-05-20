// PRIMARY NAVIGATION
// ==================
// Left sidebar with navigation links for the primary sections of the FreeNAS 10
// user interface.

"use strict";

import React from "react";

import { Link } from "react-router";

import TWBS from "react-bootstrap";
import Icon from "./Icon";

import EventBus from "./DebugTools/EventBus";

// Path definitions
// TODO: Convert to Flux or other external file
const paths =
  [ { path     : "dashboard"
    , icon     : "dashboard"
    , label    : "Dashboard"
    , status   : "danger"
    , disabled : false
    }
  , { path     : "storage"
    , icon     : "magic"
    , label    : "Storage"
    , status   : null
    , disabled : false
    }
  , { path     : "network"
    , icon     : "moon-o"
    , label    : "Network"
    , status   : null
    , disabled : false
    }
  , { path     : "sharing"
    , icon     : "cut"
    , label    : "Sharing"
    , status   : null
    , disabled : true
    }
  , { path     : "services"
    , icon     : "bitcoin"
    , label    : "Services"
    , status   : null
    , disabled : false
    }
  , { path     : "accounts"
    , icon     : "paper-plane"
    , label    : "Accounts"
    , status   : null
    , disabled : false
    }
  , { path     : "tasks"
    , icon     : "paw"
    , label    : "Tasks"
    , status   : null
    , disabled : true
    }
  , { path     : "system-tools"
    , icon     : "ambulance"
    , label    : "System Tools"
    , status   : "warning"
    , disabled : false
    }
  , { path     : "control-panel"
    , icon     : "paragraph"
    , label    : "Control Panel"
    , status   : null
    , disabled : true
    }
  , { path     : "power"
    , icon     : "plug"
    , label    : "Power"
    , status   : null
    , disabled : false
    }
  ];

const menuTiming = 600;

const PrimaryNavigation = React.createClass(

  { getInitialState: function () {
      return { expanded: true };
    }

  , componentDidMount: function () {
      // After the component has a real DOM representation, store the auto width
      // value of the navbar
      this.setState({
        fullNavWidth: this.refs.navRoot.getDOMNode().offsetWidth + "px"
      });
    }

  , handleMenuToggle: function ( event ) {
      event.stopPropagation();

      if ( this.state.expanded ) {
        this.collapseMenu();
      } else {
        this.expandMenu();
      }
    }

  , expandMenu: function () {
      const expandSequence =
        [ { elements: this.refs.navRoot.getDOMNode()
          , properties: { width: this.state.fullNavWidth }
          , options: { duration: menuTiming
                     , easing: "easeInOutBounce"
                     }
          }
        , { elements: document.getElementsByClassName( "nav-item-label" )
          , properties: "fadeIn"
          , options: { duration: menuTiming
                     , sequenceQueue: false
                     , complete: this.setState({ expanded: true })
                     }
          }
        ];

      Velocity.RunSequence( expandSequence );
    }

  , collapseMenu: function () {
      const collapseSequence =
        [ { elements: this.refs.navRoot.getDOMNode()
          , properties: { width: "60px" }
          , options: { duration: menuTiming
                     , easing: "easeInOutBounce"
                     }
          }
        , { elements: document.getElementsByClassName( "nav-item-label" )
          , properties: "fadeOut"
          , options: { duration: menuTiming
                     , sequenceQueue: false
                     , complete: this.setState({ expanded: false })
                     }
          }
        ];

      Velocity.RunSequence( collapseSequence );
    }

  , createNavItem ( rawItem, index ) {
      if ( rawItem["disabled"] ) {
        return (
          <li
            role = "presentation"
            className = "nav-item disabled"
            key = { index } >
            <a href = "#">
              <Icon
                glyph = { rawItem["icon"] }
                badgeContent = { rawItem["status"]
                             ? "!"
                             : "" /* TODO: Better content, from Flux store */
                             }
                badgeStyle = { rawItem["status"] } />
              <span className = "nav-item-label" >{ rawItem["label"] }</span>
            </a>
          </li>
        );
      } else {
        return (
          <li
            role = "presentation"
            className = "nav-item"
            key = { index } >
            <Link to = { rawItem["path"] } >
              <Icon
                glyph = { rawItem["icon"] }
                badgeContent = { rawItem["status"]
                             ? "!"
                             : "" /* TODO: Better content, from Flux store */
                             }
                badgeStyle = { rawItem["status"] } />
              <span className = "nav-item-label" >{ rawItem["label"] }</span>
            </Link>
          </li>
        );
      }
    }

  , render: function () {
      // TODO: Revert changes made for #7908 once externally resolved.
      return (
        <TWBS.Nav
          stacked
          ref = "navRoot"
          className = "primary-nav" >
          <div
            className = "primary-nav-label-toggle"
            onClick = { this.handleMenuToggle } >
            {"…"}
          </div>

          { paths.map( this.createNavItem ) }

          <button
            className="btn btn-info primary-nav-debug-button"
            onClick={ EventBus.emitToggle.bind( EventBus ) }>
            Toggle Debug Tools
          </button>

        </TWBS.Nav>
      );
    }

});

module.exports = PrimaryNavigation;
