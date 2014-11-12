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
        , { duration: 1500,
            easing: "easeInOutBounce",
            complete: this.menuCollapse
          }
        );

        Velocity(document.getElementsByClassName("anchorText")
        , "fadeOut"
        , { duration: 300
          }
        );

      //this.setState({epxandedClass: "collapsed"});
    }
    else
    {
        Velocity(this.refs.leftMenuRef.getDOMNode()
        , { width: "230px;" }
        , { duration: 1500,
            easing: "easeInOutBounce",
            complete: this.menuCollapse
          }
        );

        Velocity(document.getElementsByClassName("anchorText")
        , "fadeIn"
        , { delay: 1000,
            duration: 300
          }
        );
      //this.setState({epxandedClass: "expanded"});
    } 


    // Fade in blurred background image and show the initial text

  },

  render: function() {
    return (
      <div ref="leftMenuRef" className={"leftMenu "  + this.state.epxandedClass}>
        <div className="leftMenuContent">
        <div className="ellipsis" onClick={this.animMenu}>{ String.fromCharCode(8230) }</div>
                <ul>
                  <li><Link to="dashboard"><Icon glyph="dashboard" icoClass="icoAlert" warningFlag="!" /><span className="anchorText">Dashboard</span></Link></li>
                  <li><Link to="accounts"><Icon glyph="paper-plane" /><span className="anchorText">Accounts</span></Link></li>
                  <li><Link to="tasks"><Icon glyph="paw" /><span className="anchorText">Tasks</span></Link></li>          
                  <li><Link to="network"><Icon glyph="moon-o" /><span className="anchorText">Network</span></Link></li>
                  <li><Link to="storage"><Icon glyph="magic" /><span className="anchorText">Storage</span></Link></li>
                  <li><Link to="sharing"><Icon glyph="cut" /><span className="anchorText">Sharing</span></Link></li>                    
                  <li><Link to="services"><Icon glyph="bitcoin" /><span className="anchorText">Services</span></Link></li>          
                  <li><Link to="system-tools"><Icon glyph="ambulance" icoClass="icoAlert" warningFlag="!" /><span className="anchorText">System Tools</span></Link></li>
                  <li><Link to="control-panel"><Icon glyph="paragraph" /><span className="anchorText">Control Panel</span></Link></li>
                  <li><Link to="power"><Icon glyph="plug" /><span className="anchorText">Power</span></Link></li>
                </ul>
        </div>
      </div>
    );
  }
});

module.exports = LeftMenu;





