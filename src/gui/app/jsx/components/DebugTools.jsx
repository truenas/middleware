// DEBUG TOOLS
// ===========
// A simple pane that acts as a companion to the development tools in your
// browser. Offers direct access to the middleware connection FreeNAS is using,
// as well as some debugging helpers.

"use strict";

var React = require("react");
var TWBS  = require("react-bootstrap");

// Tabs
var RPC = require("./DebugTools/RPC");

// Local variables
var initialPanelHeight;
var initialY;

var DebugTools = React.createClass({

    getInitialState: function() {
      return {
          isVisible   : false
        , panelHeight : 350
      };
    }

  , handleResizeStart: function( event ) {
      event.stopPropagation();
      event.preventDefault();

      initialPanelHeight = this.state.panelHeight;
      initialY           = event.nativeEvent.clientY;

      window.addEventListener("mouseup", this.handleResizeStop);
      window.addEventListener("mousemove", this.handleResizeProgress );
    }

  , handleResizeProgress: function( event, foo ) {
      this.setState({
        panelHeight: initialPanelHeight - ( event.clientY - initialY )
      });
    }

  , handleResizeStop: function( event ) {
      event.stopPropagation();
      event.preventDefault();

      window.removeEventListener("mouseup", this.handleResizeStop);
      window.removeEventListener("mousemove", this.handleResizeProgress);
    }

  , handleKeypress: function( event ) {
      if ( event.which === 192 && event.ctrlKey && event.shiftKey ) {

        if ( this.state.isVisible ) {
          this.setState({ isVisible: false });
        } else {
          this.setState({ isVisible: true });
        }

      }
    }

  , componentDidMount: function() {
      window.addEventListener("keyup", this.handleKeypress );
    }

  , componentWillUnmount: function() {
      window.removeEventListener("keyup", this.handleKeypress );
    }

  , render: function() {
    var content = null;

    if ( this.state.isVisible ) {
      content = (
        <div className = "debug-panel"
             style     = {{ height: this.state.panelHeight + "px" }} >

          <TWBS.TabbedArea className   = "debug-nav"
                           onMouseDown = { this.handleResizeStart } >

            {/* RPC Interface */}
            <TWBS.TabPane eventKey={1} tab="RPC">
              <RPC />
            </TWBS.TabPane>

            {/* Event Log */}
            <TWBS.TabPane eventKey={2} tab="Events">

            </TWBS.TabPane>

            {/* Subscriptions List */}
            <TWBS.TabPane eventKey={3} tab="Subscriptions">

            </TWBS.TabPane>

            {/* Task Log and Queue */}
            <TWBS.TabPane eventKey={4} tab="Tasks">

            </TWBS.TabPane>

            {/* Stats Interface */}
            <TWBS.TabPane eventKey={5} tab="Stats">

            </TWBS.TabPane>

            {/* Debugging Options */}
            <TWBS.TabPane eventKey={6} tab="Options">

            </TWBS.TabPane>

            {/* Web Console */}
            <TWBS.TabPane eventKey={7} tab="Terminal">

            </TWBS.TabPane>

          </TWBS.TabbedArea>

        </div>
      );
    }

    return content;
  }

});

module.exports = DebugTools;
