/** @jsx React.DOM */

"use strict";

var React = require("react");

var Router = require("react-router");
var Link   = Router.Link;

var Icon   = require("./Icon");

var LeftMenu = React.createClass({
    getInitialState: function() {
    return {
      epxandedClass: "expanded"
    };
  },

  menuCollapse: function(e) {
    if (this.state.epxandedClass === "expanded")
    {
      this.setState({epxandedClass: "collapsed"});
    }
    else
    {
      this.setState({epxandedClass: "expanded"});
    }
    
  },

   animMenu: function() {
       if (this.state.epxandedClass === "expanded")
    {
      Velocity(this.refs.leftMenuRef.getDOMNode()
      , { width: "44px;" }
      , { delay: 200,
          duration: 1500,
          easing: "linear",
          complete: this.menuCollapse
        }
      );

      //this.setState({epxandedClass: "collapsed"});
    }
    else
    {
      this.setState({epxandedClass: "expanded"});
    } 


    // Fade in blurred background image and show the initial text

  },

  render: function() {
    return (
      <div ref="leftMenuRef" className={"leftMenu "  + this.state.epxandedClass}>
        <div className="leftMenuContent">
        <div onClick={this.animMenu}>...</div>
                <ul>
                  <li><Link to="dashboard"><Icon glyph="dashboard" icoClass="icoAlert" warningFlag="!" />Dashboard</Link></li>
                  <li><Link to="accounts"><Icon glyph="paper-plane" />Accounts</Link></li>
                  <li><Link to="tasks"><Icon glyph="paw" />Tasks</Link></li>          
                  <li><Link to="network"><Icon glyph="moon-o" />Network</Link></li>
                  <li><Link to="storage"><Icon glyph="magic" />Storage</Link></li>
                  <li><Link to="sharing"><Icon glyph="cut" />Sharing</Link></li>                    
                  <li><Link to="services"><Icon glyph="bitcoin" />Services</Link></li>          
                  <li><Link to="system-tools"><Icon glyph="ambulance" icoClass="icoAlert" warningFlag="!" />System Tools</Link></li>
                  <li><Link to="control-panel"><Icon glyph="paragraph" />Control Panel</Link></li>
                  <li><Link to="power"><Icon glyph="plug" />Power</Link></li>
                </ul>
        </div>
      </div>
    );
  }
});

module.exports = LeftMenu;





