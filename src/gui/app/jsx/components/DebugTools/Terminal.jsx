// Terminal Tab
// ============

"use strict";

import React from "react";
import TWBS from "react-bootstrap";

import ShellMiddleware from "../../middleware/ShellMiddleware";

import Shell from "../common/Shell";

var Terminal = React.createClass({

    getInitialState: function () {
      return {
          currentShell : "/bin/sh"
        , shells       : []
      };
    }

  , componentDidMount: function () {
      ShellMiddleware.requestAvailableShells( function( shells ) {
        this.setState({ shells: shells });
      }.bind( this ) );
    }

  , handleShellSelect: function( shell ) {
      this.setState({ currentShell: shell });
    }

  , createShellMenuItem: function( shell, index ) {
      return (
        <TWBS.MenuItem
            onClick = { this.handleShellSelect.bind( null, shell ) }
            key     = { index }>
          { shell }
        </TWBS.MenuItem>
      );
    }

  , render: function () {
      return (
        <div className="debug-content-flex-wrapper">

          <TWBS.Col xs={6} className="debug-column" >

            <h5 className="debug-heading">{"FreeNAS Shell: " + this.state.currentShell }</h5>
            <Shell shellType={ this.state.currentShell } />

          </TWBS.Col>

          <TWBS.Col xs={6} className="debug-column" >

            <div className="debug-column-content">
              <h5 className="debug-heading">Terminal Options</h5>
              <div>
                <label style={{ marginRight: "10px" }}>Shell Type:</label>
                <TWBS.DropdownButton bsStyle="default" title={ this.state.currentShell }>
                  { this.state.shells.map( this.createShellMenuItem ) }
                </TWBS.DropdownButton>
              </div>

              <hr />

              <h5 className="debug-heading">Term.js Instructions</h5>
              <p>While term.js has always supported copy/paste using the mouse, it now also supports several keyboard based solutions for copy/paste.</p>

              <p>term.js includes a tmux-like selection mode which makes copy and paste very simple. <code>Ctrl-A</code> enters <code>prefix</code> mode, from here you can type <code>Ctrl-V</code> to paste. Press <code>[</code> in prefix mode to enter selection mode. To select text press <code>v</code> (or <code>space</code>) to enter visual mode, use <code>hjkl</code> to navigate and create a selection, and press <code>Ctrl-C</code> to copy.</p>

              <p><code>Ctrl-C</code> (in visual mode) and <code>Ctrl-V</code> (in prefix mode) should work in any OS for copy and paste. <code>y</code> (in visual mode) will work for copying only on X11 systems. It will copy to the primary selection.</p>

              <p>Note: <code>Ctrl-C</code> will also work in prefix mode for the regular OS/browser selection. If you want to select text with your mouse and copy it to the clipboard, simply select the text and type <code>Ctrl-A + Ctrl-C</code>, and <code>Ctrl-A + Ctrl-V</code> to paste it.</p>

              <p>For Mac users: Consider <code>Ctrl</code> to be <code>Command/Apple</code> above.</p>
            </div>

          </TWBS.Col>
        </div>
      );
    }

});

module.exports = Terminal;
