define([
    "dojo/_base/declare",
    "dojo/_base/lang",
    "dojo/dom-class",
    "dijit/registry",
    "dijit/layout/ContentPane"
    ], function(declare,
    lang,
    domClass,
    registry,
    ContentPane
    ) {

    var Menu = declare("freeadmin.Menu", [], {
        constructor: function(/*Object*/ kwArgs){
            lang.mixin(this, kwArgs);
        },
        openSystem: function() {
            var opened = false;
            var opened2 = false;
            var opened3 = false;
            var p = registry.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'system.Reporting'){
                    p.selectChild(c[i]);
                    opened = true;
                } else if(c[i].tab == 'system.Settings'){
                    p.selectChild(c[i]);
                    opened2 = true;
                } else if(c[i].tab == 'system.SysInfo'){
                    p.selectChild(c[i]);
                    opened3 = true;
                }
            }
            if(opened != true) {
                var pane = new ContentPane({
                    title: gettext('Reporting'),
                    refreshOnShow: true,
                    closable: true,
                    href: this.urlReporting,
                });
                pane.tab = 'system.Reporting';
                p.addChild(pane);
            }

            if(opened2 != true) {
                var pane2 = new ContentPane({
                    id: 'settingstab',
                    title: gettext('Settings'),
                    closable: true,
                    href: this.urlSettings,
                });
                pane2.tab = 'system.Settings';
                p.addChild(pane2);
            }

            if(opened3 != true) {
                var pane3 = new ContentPane({
                    id: 'sysinfotab',
                    title: gettext('System Information'),
                    refreshOnShow: true,
                    closable: true,
                    href: this.urlInfo,
                });
                pane3.tab = 'system.SysInfo';
                p.addChild(pane3);
                p.selectChild(pane3);
            }

        },
        openNetwork: function(tab) {
            var opened = false;
            var p = registry.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'network'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(tab) {
                        var tabnet = registry.byId("tab_networksettings");
                        if(tabnet) {
                            var c2 = tabnet.getChildren();
                            for(var j=0; j<c2.length; j++){
                                if(c2[j].domNode.getAttribute("tab") == tab)
                                    tabnet.selectChild(c2[j]);
                            }
                        }
                    }

                }
            }
            if(opened != true) {
                openurl = this.urlNetwork;
                if(tab) {
                    openurl += '?tab='+tab;
                }

                var pane = new ContentPane({
                    title: gettext('Network Settings'),
                    closable: true,
                    //refreshOnShow: true,
                    href: openurl,
                });
                pane.tab = 'network';
                p.addChild(pane);
                p.selectChild(pane);
            }

        },
        openSharing: function(tab) {
            var opened = false;
            var p = registry.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'shares'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(tab) {
                        var tabnet = registry.byId("tab_sharing");
                        if(tabnet) {
                            var c2 = tabnet.getChildren();
                            for(var j=0; j<c2.length; j++){
                                if(c2[j].domNode.getAttribute("tab") == tab)
                                    tabnet.selectChild(c2[j]);
                            }
                        }
                    }
                }
            }
            if(opened != true) {
                openurl = this.urlSharing;
                if(tab) {
                    openurl += '?tab='+tab;
                }
                var pane = new ContentPane({
                    title: 'Shares',
                    closable: true,
                    //refreshOnShow: true,
                    href: openurl,
                });
                pane.tab = 'shares';
                p.addChild(pane);
                p.selectChild(pane);
            }

        },

        openPluginsFcgi: function(p, item) {
            editObject(item.name, item.url);
        },

        openServices: function(onload, svc) {
            if(!onload) onload = function() {};
            var opened = false;
            var p = registry.byId("content");
            var href = this.urlServices;
            if(svc) href += '?toggleCore=' + svc;

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'services'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(onload) lang.hitch(this, onload)();
                }
            }
            if(opened != true) {
                var pane = new ContentPane({
                    title: gettext('Services'),
                    closable: true,
                    href: href,
                    onLoad: onload,
                });
                pane.tab = 'services';
                p.addChild(pane);
                p.selectChild(pane);
                domClass.add(pane.domNode,["objrefresh", "data_services_services"]);
            }

        },

        openJails: function(tab) {
            var opened = false;
            var p = registry.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'jails'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(tab) {
                        var tabnet = registry.byId("tab_jails");
                        if(tabnet) {
                            var c2 = tabnet.getChildren();
                            for(var j=0; j<c2.length; j++){
                                if(c2[j].domNode.getAttribute("tab") == tab)
                                    tabnet.selectChild(c2[j]);
                            }
                        }
                    }
                }
            }
            if(opened != true) {
                openurl = this.urlJails;
                if(tab) {
                    openurl += '?tab='+tab;
                }
                var pane = new ContentPane({
                    title: gettext('Jails'),
                    closable: true,
                    href:openurl,
                });
                pane.tab = 'jails';
                p.addChild(pane);
                p.selectChild(pane);
                domClass.add(pane.domNode,["objrefresh", "data_jails_jails"]);
            }
        },

        openPlugins: function(tab) {
            var opened = false;
            var p = registry.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'plugins'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(tab) {
                        var tabnet = registry.byId("tab_jails");
                        if(tabnet) {
                            var c2 = tabnet.getChildren();
                            for(var j=0; j<c2.length; j++){
                                if(c2[j].domNode.getAttribute("tab") == tab)
                                    tabnet.selectChild(c2[j]);
                            }
                        }
                    }
                }
            }
            if(opened != true) {
                openurl = this.urlPlugins;
                if(tab) {
                    openurl += '?tab='+tab;
                }
                var pane = new ContentPane({
                    title: gettext('Plugins'),
                    closable: true,
                    href: openurl,
                });
                pane.tab = 'plugins';
                p.addChild(pane);
                p.selectChild(pane);
                domClass.add(pane.domNode,["objrefresh", "data_plugins_plugins"]);
            }
        },

        openAccount: function(tab) {
            var opened = false;
            var p = registry.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'account'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(tab) {
                        var tabnet = registry.byId("tab_account");
                        if(tabnet) {
                            var c2 = tabnet.getChildren();
                            for(var j=0; j<c2.length; j++){
                                if(c2[j].domNode.getAttribute("tab") == tab)
                                    tabnet.selectChild(c2[j]);
                            }
                        }
                    }

                }
            }
            if(opened != true) {
                openurl = this.urlAccount;
                if(tab) {
                    openurl += '?tab='+tab;
                }
                var pane = new ContentPane({
                    title: gettext('Account'),
                    closable: true,
                    href:openurl,
                });
                pane.tab = 'account';
                p.addChild(pane);
                p.selectChild(pane);

            }

        },

        openStorage: function(tab) {
            var opened = false;
            var p = registry.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'storage'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(tab) {
                        var tabnet = registry.byId("tab_storage");
                        if(tabnet) {
                            var c2 = tabnet.getChildren();
                            for(var j=0; j<c2.length; j++){
                                if(c2[j].domNode.getAttribute("tab") == tab)
                                    tabnet.selectChild(c2[j]);
                            }
                        }
                    }
                }
            }
            if(opened != true) {
                openurl = this.urlStorage;
                if(tab) {
                    openurl += '?tab='+tab;
                }
                var pane = new ContentPane({
                    title: gettext('Storage'),
                    closable: true,
                    href:openurl,
                });
                pane.tab = 'storage';
                p.addChild(pane);
                p.selectChild(pane);
                domClass.add(pane.domNode,["objrefresh", "data_storage_Volumes"]);

            }

        },
        openISCSI: function(tab) {
            var opened = false;
            var p = registry.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'iscsi'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(tab) {
                        var tabnet = registry.byId("tab_iscsi");
                        if(tabnet) {
                            var c2 = tabnet.getChildren();
                            for(var j=0; j<c2.length; j++){
                                if(c2[j].domNode.getAttribute("tab") == tab)
                                    tabnet.selectChild(c2[j]);
                            }
                        }
                    }

                }
            }
            if(opened != true) {
                openurl = this.urlISCSI;
                if(tab) {
                    openurl += '?tab='+tab;
                }

                var pane = new ContentPane({
                    title: 'iSCSI',
                    closable: true,
                    //refreshOnShow: true,
                    href: openurl,
                });
                pane.tab = 'iscsi';
                p.addChild(pane);
                p.selectChild(pane);
            }

        }

    });
    return Menu;

});
