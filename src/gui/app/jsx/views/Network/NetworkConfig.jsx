// Network Configuration Overview
// ==============================

"use strict";

import React from "react";
import TWBS from "react-bootstrap"


const NetworkConfig = React.createClass({


  render: function () {
      return (
        <main>
          <div className = "network-config container-fluid">
            <TWBS.PanelGroup>
              <TWBS.Panel>
                <TWBS.ListGroup fill>
                  <TWBS.ListGroupItem className = "network-attribute"/>
                  <TWBS.ListGroupItem className = "network-attribute"/>
                </TWBS.ListGroup>
              </TWBS.Panel>
              <TWBS.Panel>
                <TWBS.ListGroup fill>
                  <TWBS.ListGroupItem className = "network-attribute"/>
                  <TWBS.ListGroupItem className = "network-attribute"/>
                </TWBS.ListGroup>
              </TWBS.Panel>
            </TWBS.PanelGroup>
          </div>
        </main> )
    }

});

export default NetworkConfig;
