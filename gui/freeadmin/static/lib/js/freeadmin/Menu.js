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
        openSystem: function(tab) {
            var opened = false;
            var p = registry.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
              if(c[i].tab == 'system'){
                p.selectChild(c[i]);
                opened = c[i];
                if(tab) {
                    var tabnet = registry.byId("tab_systemsettings");
                    if(tabnet) {
                        var c2 = tabnet.getChildren();
                        for(var j=0; j<c2.length; j++){
                            if(c2[j].domNode.getAttribute("tab") == tab)
                                tabnet.selectChild(c2[j]);
                        }
                    }
                } else {
                    c[i].refresh();
                }
              } else {
                p.removeChild(c[i]);
                c[i].destroy();
              }
            }

            if(opened == false) {
                openurl = this.urlSystem;
                if(tab) {
                    openurl += '?tab='+tab;
                }
                var pane = new ContentPane({
                    title: gettext('System'),
                    closable: false,
                    href: openurl
                });
                pane.tab = 'system';
                p.addChild(pane);
                p.selectChild(pane);
            }

        },
        openTasks: function(tab) {
            var opened = false;
            var p = registry.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
              if(c[i].tab == 'tasks'){
                p.selectChild(c[i]);
                opened = c[i];
                if(tab) {
                    var tabnet = registry.byId("tab_tasks");
                    if(tabnet) {
                        var c2 = tabnet.getChildren();
                        for(var j=0; j<c2.length; j++){
                            if(c2[j].domNode.getAttribute("tab") == tab)
                                tabnet.selectChild(c2[j]);
                        }
                    }
                } else {
                    c[i].refresh();
                }
              } else {
                p.removeChild(c[i]);
                c[i].destroy();
              }
            }

            if(opened == false) {
                openurl = this.urlTasks;
                if(tab) {
                    openurl += '?tab='+tab;
                }
                var pane = new ContentPane({
                    title: gettext('Tasks'),
                    closable: false,
                    href: openurl
                });
                pane.tab = 'tasks';
                p.addChild(pane);
                p.selectChild(pane);
            }

        },
        openVM: function(tab) {
            var opened = false;
            var p = registry.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
              if(c[i].tab == 'vm'){
                p.selectChild(c[i]);
                opened = c[i];
                if(tab) {
                    var tabnet = registry.byId("tab_vm");
                    if(tabnet) {
                        var c2 = tabnet.getChildren();
                        for(var j=0; j<c2.length; j++){
                            if(c2[j].domNode.getAttribute("tab") == tab)
                                tabnet.selectChild(c2[j]);
                        }
                    }
                } else {
                    c[i].refresh();
                }
              } else {
                p.removeChild(c[i]);
                c[i].destroy();
              }
            }

            if(opened == false) {
                openurl = this.urlTasks;
                if(tab) {
                    openurl += '?tab='+tab;
                }
                var pane = new ContentPane({
                    title: gettext('VMs'),
                    closable: false,
                    href: openurl
                });
                pane.tab = 'vm';
                p.addChild(pane);
                p.selectChild(pane);
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
                    } else {
                        c[i].refresh();
                    }

                } else {
                  p.removeChild(c[i]);
                  c[i].destroy();
                }
            }

            if(opened != true) {
                openurl = this.urlNetwork;
                if(tab) {
                    openurl += '?tab='+tab;
                }

                var pane = new ContentPane({
                    title: gettext('Network'),
                    closable: false,
                    //refreshOnShow: true,
                    href: openurl,
                });
                pane.tab = 'network';
                p.addChild(pane);
                p.selectChild(pane);
            }

        },
        openVcp: function(tab) {
            var opened = false;
            var p = registry.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'vcp'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(tab) {
                        var tabnet = registry.byId("tab_vcpconfiguration");
                        if(tabnet) {
                            var c2 = tabnet.getChildren();
                            for(var j=0; j<c2.length; j++){
                                if(c2[j].domNode.getAttribute("tab") == tab)
                                    tabnet.selectChild(c2[j]);
                            }
                        }
                    } else {
                         p.removeChild(c[i]);
                         c[i].destroy();
                         opened=false;
                    }

                } else {
                  p.removeChild(c[i]);
                  c[i].destroy();
                }
            }

            if(opened != true) {
                openurl = this.urlVcp;
                if(tab) {
                    openurl += '?tab='+tab;
                }

                var pane = new ContentPane({
                    title: gettext('vCenter Plugin Configuration'),
                    closable: false,
                    //refreshOnShow: true,
                    href: openurl,
                });
                pane.tab = 'vcp';
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
                    } else {
                        c[i].refresh();
                    }
                } else {
                  p.removeChild(c[i]);
                  c[i].destroy();
                }
            }
            if(opened != true) {
                openurl = this.urlSharing;
                if(tab) {
                    openurl += '?tab='+tab;
                }
                var pane = new ContentPane({
                    title: gettext('Sharing'),
                    closable: false,
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
                    c[i].href = href;
                    p.selectChild(c[i]);
                    c[i].refresh();
                    opened = true;
                    if(onload) lang.hitch(this, onload)();
                } else {
                  p.removeChild(c[i]);
                  c[i].destroy();
                }
            }
            if(opened != true) {
                var pane = new ContentPane({
                    title: gettext('Services'),
                    closable: false,
                    href: href,
                    onLoad: function() {
                      onload();
                      // Do not refresh with ?toggleCore twice
                      pane.href = pane.href.split('?')[0];
                    },
                    refreshOnShow: true
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
                    } else {
                        c[i].refresh();
                    }
                } else {
                  p.removeChild(c[i]);
                  c[i].destroy();
                }
            }
            if(opened != true) {
                openurl = this.urlJails;
                if(tab) {
                    openurl += '?tab='+tab;
                }
                var pane = new ContentPane({
                    title: gettext('Jails'),
                    closable: false,
                    href:openurl,
                    refreshOnShow: true
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
                    } else {
                        c[i].refresh();
                    }
                } else {
                  p.removeChild(c[i]);
                  c[i].destroy();
                }
            }
            if(opened != true) {
                openurl = this.urlPlugins;
                if(tab) {
                    openurl += '?tab='+tab;
                }
                var pane = new ContentPane({
                    title: gettext('Plugins'),
                    closable: false,
                    href: openurl,
                    refreshOnShow: true
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
                    } else {
                        c[i].refresh();
                    }

                } else {
                  p.removeChild(c[i]);
                  c[i].destroy();
                }
            }
            if(opened != true) {
                openurl = this.urlAccount;
                if(tab) {
                    openurl += '?tab='+tab;
                }
                var pane = new ContentPane({
                    title: gettext('Account'),
                    closable: false,
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
                    } else {
                        c[i].refresh();
                    }
                } else {
                  p.removeChild(c[i]);
                  c[i].destroy();
                }
            }
            if(opened != true) {
                openurl = this.urlStorage;
                if(tab) {
                    openurl += '?tab='+tab;
                }
                var pane = new ContentPane({
                    title: gettext('Storage'),
                    closable: false,
                    href: openurl,
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
                    } else {
                        c[i].refresh();
                    }

                } else {
                  p.removeChild(c[i]);
                  c[i].destroy();
                }
            }
            if(opened != true) {
                openurl = this.urlISCSI;
                if(tab) {
                    openurl += '?tab='+tab;
                } else {
                    openurl += '?tab=services.ISCSI';
                }

                var pane = new ContentPane({
                    title: 'Sharing',
                    closable: false,
                    //refreshOnShow: true,
                    href: openurl,
                });
                pane.tab = 'shares';
                p.addChild(pane);
                p.selectChild(pane);
            }

        },

        openSupport: function(onload) {
            if(!onload) onload = function() {};
            var opened = false;
            var p = registry.byId("content");
            var href = this.urlSupport;

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'support'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(onload) lang.hitch(this, onload)();
                }
            }
            if(opened != true) {
                var pane = new ContentPane({
                    title: gettext('Support'),
                    closable: true,
                    href: href,
                    onLoad: onload,
                });
                pane.tab = 'support';
                p.addChild(pane);
                p.selectChild(pane);
                domClass.add(pane.domNode,["objrefresh", "data_support_support"]);
            }

        },

        openDocumentation: function() {
            var opened = false;
            var p = registry.byId("content");

            var c = p.getChildren();
            for (var i=0; i<c.length; i++){
                if(c[i].tab == 'documentation') {
                    p.selectChild(c[i]);
                    opened = true;
                } else {
                    p.removeChild(c[i]);
                    c[i].destroy();
                }
            }
            
            if(opened != true) {

                openurl = this.urlDocumentation;

                var pane = new ContentPane({
                    title: gettext('Documentation'),
                    closable: false,
                    href: openurl,
                });
                p.addChild(pane);
                p.selectChild(pane);
                domClass.add(pane.domNode,["objrefresh", "data_documentation_documentation"]);
            }

        },

        openDirectoryService: function(tab) {
            var opened = false;
            var p = registry.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'directoryservice'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(tab) {
                        var tabnet = registry.byId("tab_directoryservice");
                        if(tabnet) {
                            var c2 = tabnet.getChildren();
                            for(var j=0; j<c2.length; j++){
                                if(c2[j].domNode.getAttribute("tab") == tab)
                                    tabnet.selectChild(c2[j]);
                            }
                        }
                    } else {
                        c[i].refresh();
                    }
                } else {
                  p.removeChild(c[i]);
                  c[i].destroy();
                }
            }
            if(opened != true) {
                openurl = this.urlDirectoryService;
                if(tab) {
                    openurl += '?tab='+tab;
                }
                var pane = new ContentPane({
                    title: gettext('Directory Service'),
                    closable: false,
                    href:openurl,
                    refreshOnShow: true
                });
                pane.tab = 'directoryservice';
                p.addChild(pane);
                p.selectChild(pane);
                domClass.add(pane.domNode,["objrefresh", "data_directoryservice_directoryservice"]);
            }
        },

    });

    return Menu;

});
