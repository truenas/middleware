/** @jsx React.DOM */

// Main App Wrapper
// ================
// Top level controller-view for FreeNAS webapp
"use strict";


var React  = require("react");

// Page router
var Router = require("react-router");
var Link   = Router.Link;

// Twitter Bootstrap React components
var TWBS   = require("react-bootstrap");

var FreeNASWebApp = React.createClass({
  render: function() {
    return (
      <div>
      <div className="navBar">Notification Bar will live here!</div>
      <div className="leftMenu">
        <ul>
          <li><Link to="dashboard" className="ico-dashboard">Dashboard</Link></li>
          <li><Link to="accounts" className="ico-accounts node">Accounts</Link>
            <ul>
              <li><Link to="users" className="ico-users">Users</Link></li>
              <li><Link to="groups" className="ico-groups">Groups</Link></li>
            </ul>
          </li>
          <li><Link to="tasks" className="ico-tasks node">Tasks</Link>
            <ul>
              <li><Link to="scrubs" className="ico-Scrubs">Scrubs</Link></li>
              <li><Link to="cron-jobs" className="ico-cron-jobs">Cron Jobs</Link></li>
              <li><Link to="init-shutdown-scripts" className="ico-init-shutdown-scripts">Init-Shutdown Scripts</Link></li>
              <li><Link to="rsync-jobs" className="ico-rsync-jobs">Rsync Jobs</Link></li>
              <li><Link to="smart-tests" className="ico-smart-tests">SMART Tests</Link></li>
              <li><Link to="periodic-snapshots" className="ico-periodic-snapshots">Periodic Snapshots</Link></li>
              <li><Link to="replication-tasks" className="ico-replication-tasks">Replication Tasks</Link></li>
              <li><Link to="tasks-overview" className="ico-tasks-overview">All jobs / Overview </Link></li>                                          
            </ul>
          </li>          
          <li><Link to="network" className="ico-network mode">Network</Link>
            <ul>
              <li><Link to="interfaces" className="ico-interfaces">Interfaces</Link></li>
              <li><Link to="link-aggregation" className="ico-link-aggregation">"Link Aggregation"</Link></li>
              <li><Link to="lagg-members" className="ico-lagg-members">LAGG members</Link></li>
              <li><Link to="static-routes" className="ico-static-routes">Static Routes</Link></li>
              <li><Link to="vlans" className="ico-vlans">VLANs</Link></li>
            </ul>
          </li>
          <li><Link to="storage" className="ico-storage node">Storage</Link>
            <ul>
              <li><Link to="Volumes" className="ico-volumes">Volumes</Link></li>
              <li><Link to="Disks" className="ico-disks">Disks</Link></li>
              <li><Link to="Snapshots" className="ico-snapshots">Snapshots</Link></li>
            </ul>
          </li>
          <li><Link to="sharing" className="ico-sharing node">Sharing</Link>
            <ul>
              <li><Link to="afp" className="ico-afp">AFP</Link></li>
              <li><Link to="cifs" className="ico-cifs">CIFS</Link></li>
              <li><Link to="nfs" className="ico-nfs">NFS</Link></li>
              <li><Link to="webdav" className="ico-webdav">WebDAV</Link></li>
            </ul>
          </li>                    
          <li><Link to="services" className="ico-services">Services</Link></li>          
          <li><Link to="system-tools" className="ico-system-tools node">System Tools</Link>
            <ul>
              <li><Link to="file-browser" className="ico-file-browser">File Browser</Link></li>
              <li><Link to="shell" className="ico-shell">Shell</Link></li>
            </ul>
          </li>
          <li><Link to="control-panel" className="ico-control-panel">Control Panel</Link></li>
          <li><Link to="power" className="ico-power node">Power</Link>
            <ul>
              <li><Link to="restart" className="ico-restart">Restart</Link></li>
              <li><Link to="shutdown" className="ico-shutdown">Shutdown</Link></li>
            </ul>
          </li>
        </ul>
      </div>
      <TWBS.Grid className="mainGrid">
        {/* TODO: Add Modal mount div */}
        <TWBS.Row>
          {/* Navigation side menu */}
          <TWBS.Col xs={2} sm={2} md={2} lg={2} xl={2}>

          </TWBS.Col>

          {/* Primary view */}
          <TWBS.Col xs={8} sm={8} md={8} lg={8} xl={8}>
            <h1>FreeNAS WebGUI</h1>
            { this.props.activeRouteHandler() }
          </TWBS.Col>

          {/* Tasks and active users */}
          <TWBS.Col xs={2} sm={2} md={2} lg={2} xl={2}>
            {/* TODO: Add tasks/users component */}
          </TWBS.Col>
        </TWBS.Row>
      </TWBS.Grid>
      </div>
    );
  }
});

module.exports = FreeNASWebApp;