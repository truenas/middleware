/*-
 * Copyright (c) 2011 iXsystems, Inc.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 *
 */

    /*
     * Menu Object
     * Responsible for opening menu tabs
     * URLs are loaded OnLoad from djang reverse()
     */
    var Menu = {

        openSystem: function() {
            var opened = false;
            var opened2 = false;
            var opened3 = false;
            var p = dijit.byId("content");

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
                var pane = new dijit.layout.ContentPane({
                    title: gettext('Reporting'),
                    refreshOnShow: true,
                    closable: true,
                    href: this.urlReporting,
                });
                pane.tab = 'system.Reporting';
                p.addChild(pane);
            }

            if(opened2 != true) {
                var pane2 = new dijit.layout.ContentPane({
                    id: 'settingstab',
                    title: gettext('Settings'),
                    closable: true,
                    href: this.urlSettings,
                });
                pane2.tab = 'system.Settings';
                p.addChild(pane2);
            }

            if(opened3 != true) {
                var pane3 = new dijit.layout.ContentPane({
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
            var p = dijit.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'network'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(tab) {
                        var tabnet = dijit.byId("tab_networksettings");
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

                var pane = new dijit.layout.ContentPane({
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
            var p = dijit.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'shares'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(tab) {
                        var tabnet = dijit.byId("tab_sharing");
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
                var pane = new dijit.layout.ContentPane({
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

	openPlugins: function(onload) {
            if(!onload) onload = function() {};
            var opened = false;
            var p = dijit.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'plugins'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(onload) onload();
                }
            }
            if(opened != true) {
                var pane = new dijit.layout.ContentPane({
                    title: gettext('Plugins'),
                    closable: true,
                    href: this.urlPlugins,
                    onLoad: onload,
                });
                pane.tab = 'plugins';
                p.addChild(pane);
                p.selectChild(pane);
                dojo.addClass(pane.domNode,["objrefresh", "data_sharing_UNIX"]);
            }
	},

        openPluginsFcgi: function(p, item) {
            dojo.xhrGet({
                url: item.url,
                sync: true,
                failOk: true,
                handleAs: "json",
                load: function(data) {

/*
                    i = 0;
                    inputs = new Array();
                    form = new dijit.form.Form(); 
                    for (var key in data) {
                        val = data[key]
                        inputs[i] = new dijit.form.TextBox({
                            name: key,
                            value: val, 
                        });
                    }
*/

/*
                    json = dojo.toJson(data);
                    dialog = new dijit.Dialog({
                        id: "pluginsfcgi_dialog",
                        style: "max-width: 75%;max-height:70%;background-color:white;overflow:auto;",
                        name: item.name,
                        onHide: function() {
                            setTimeout(dojo.hitch(this, 'destroyRecursive'), dijit.defaultDuration);
                            refreshTabs(attrs.nodes);
                        },
                        onLoad: function() {
                            processStack();
                            this.layout();
                       }
                    });
                    dialog.set('title', item.name);
                    dialog.set('content', json); 
                    dialog.show();
*/

                    //editObject(item.name, item.url);
                }, 
            });
        },

        openServices: function(onload) {
            if(!onload) onload = function() {};
            var opened = false;
            var p = dijit.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[I].tab == 'services'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(onload) onload();
                }
            }
            if(opened != true) {
                var pane = new dijit.layout.ContentPane({
                    title: gettext('Services'),
                    closable: true,
                    href: this.urlServices,
                    onLoad: onload,
                });
                pane.tab = 'services';
                p.addChild(pane);
                p.selectChild(pane);
                dojo.addClass(pane.domNode,["objrefresh", "data_sharing_UNIX"]);
            }

        },

        openAccount: function(tab) {
            var opened = false;
            var p = dijit.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'account'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(tab) {
                        var tabnet = dijit.byId("tab_account");
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
                var pane = new dijit.layout.ContentPane({
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
            var p = dijit.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'storage'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(tab) {
                        var tabnet = dijit.byId("tab_storage");
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
                var pane = new dijit.layout.ContentPane({
                    title: gettext('Storage'),
                    closable: true,
                    href:openurl,
                });
                pane.tab = 'storage';
                p.addChild(pane);
                p.selectChild(pane);
                dojo.addClass(pane.domNode,["objrefresh", "data_storage_Volumes"]);

            }

        },
        openISCSI: function(tab) {
            var opened = false;
            var p = dijit.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'iscsi'){
                    p.selectChild(c[i]);
                    opened = true;
                    if(tab) {
                        var tabnet = dijit.byId("tab_iscsi");
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

                var pane = new dijit.layout.ContentPane({
                    title: 'iSCSI',
                    closable: true,
                    //refreshOnShow: true,
                    href: openurl,
                });
                pane.tab = 'iscsi';
                p.addChild(pane);
                p.selectChild(pane);
            }

        },
        openCron: function() {
            var opened = false;
            var p = dijit.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'cron'){
                    p.selectChild(c[i]);
                    opened = true;
                }
            }
            if(opened != true) {
                openurl = this.urlCron;

                var pane = new dijit.layout.ContentPane({
                    title: gettext('CronJobs'),
                    closable: true,
                    refreshOnShow: true,
                    href: openurl,
                });
                pane.tab = 'cron';
                p.addChild(pane);
                p.selectChild(pane);
                dojo.addClass(pane.domNode,["objrefresh", "data_services_CronJob"]);
            }

        }

    };
    /* end Menu */

    restartHttpd = function(newurl) {

        dojo.xhrGet({
            url: '/system/restart-httpd/',
            sync: true,
            failOk: true,
            handle: function(a1,a2) {
                setTimeout(function () {
                    window.location = newurl;
                }, 1500);
            },
        });

    }

    ask_service = function(srv) {

        dialog = new dijit.Dialog({
            title: 'Enable service',
            href: '/services/enable/'+srv+'/',
            parseOnLoad: true,
            closable: true,
            style: "max-width: 75%;max-height:70%;background-color:white;overflow:auto;",
            onHide: function() {
                setTimeout(dojo.hitch(this, 'destroyRecursive'), dijit.defaultDuration);
            },
        });
        dialog.show();

    }

    addAlias = function(a, name) {

        extra = dijit.byId("id_"+name+"-TOTAL_FORMS");
        var extran = extra.get("value");
        n4a = new dijit.form.TextBox({
            name: name+"-"+extran+"-alias_v4address",
            id: "id_"+name+"-"+extran+"-alias_v4address",
            value: "",
        });

        getid4 = dijit.byId("id_"+name+"-"+(parseInt(extran)-1)+"-alias_v4netmaskbit");
        n4n = new dijit.form.Select({
            name: name+"-"+extran+"-alias_v4netmaskbit",
            id: "id_"+name+"-"+extran+"-alias_v4netmaskbit",
            value: "",
            options: getid4.options,
        });

        n6a = new dijit.form.TextBox({
            name: name+"-"+extran+"-alias_v6address",
            id: "id_"+name+"-"+extran+"-alias_v6address",
            value: "",
        });

        getid6 = dijit.byId("id_"+name+"-"+(parseInt(extran)-1)+"-alias_v6netmaskbit");
        n6n = new dijit.form.Select({
            name: name+"-"+extran+"-alias_v6netmaskbit",
            id: "id_"+name+"-"+extran+"-alias_v6netmaskbit",
            value: "",
            options: getid6.options,
        });

        ni = new dijit.form.TextBox({
            name: name+"-"+extran+"-id",
            id: "id_"+name+"-"+extran+"-id",
            type: "hidden",
        });

        var tr = dojo.create("tr");
        var td = dojo.create("td", null, tr);
        dojo.attr(td, "colspan", "2");
        dojo.query(a.parentNode.parentNode).before(tr);
        var table = dojo.create("table", null, td);

        var tr = dojo.create("tr", null, table);
        var td = dojo.create("td", null, tr);
        dojo.attr(td, "colspan", "2");
        new dijit.layout.ContentPane({
            id: "id_"+name+"-"+extran+"-__all__"
        }).placeAt(td);

        var tr = dojo.create("tr", null, table);
        var td1 = dojo.create("th", {innerHTML: "IPv4 Address"}, tr, "last");
        var td2 = dojo.create("td", null, tr, "last");
        n4a.placeAt(td2);
        ni.placeAt(td2);

        var tr = dojo.create("tr", null, table);
        var td1 = dojo.create("th", {innerHTML: "IPv4 Netmask"}, tr, "last");
        var td2 = dojo.create("td", null, tr, "last");
        n4n.placeAt(td2);

        var tr = dojo.create("tr", null, table);
        var td1 = dojo.create("th", {innerHTML: "IPv6 Address"}, tr, "last");
        var td2 = dojo.create("td", null, tr, "last");
        n6a.placeAt(td2);

        ni.placeAt(td2);

        var tr = dojo.create("tr", null, table);
        var td1 = dojo.create("th", {innerHTML: "IPv6 Netmask"}, tr, "last");
        var td2 = dojo.create("td", null, tr, "last");
        n6n.placeAt(td2);

        extra.set('value', parseInt(extran) + 1);
    }

    toggle_service = function(obj) {
        var td = obj.parentNode;
        var n = dojo.create("div", {  }, td);
        dojo.addClass(n, "dijitIconLoading");
        dojo.style(n, "height", "25px");
        dojo.style(n, "float", "left");

        var xhrArgs = {
            url: "/services/toggle/"+obj.name+"/",
            postData: "Some random text",
            handleAs: "json",
            load: function(data) {
                if(data.status == 'on') {
                    obj.src = '/media/images/ui/buttons/on.png';
                } else if(data.status == 'off') {
                    obj.src = '/media/images/ui/buttons/off.png';
                }
                if(data.error) {
                    setMessage(data.message, "error");
                }
                dojo.destroy(n);
            },
            error: function(error) {
                //alert
            }
        }
        var deferred = dojo.xhrPost(xhrArgs);

    }

    buttongrid = function(v) {
        var json = dojo.fromJson(v);
        dojo.parser.parse(dojo.byId(this.id));
        var gridhtml = dijit.getEnclosingWidget(dojo.byId(this.id));

        var content = new dijit.layout.ContentPane({});
        var b = new dijit.form.Button({label: gettext("Edit")});

        dojo.connect(b.domNode, 'onclick', function(){ editObject(gettext('Edit Disk'), json.edit_url, [gridhtml,]); });
        content.domNode.appendChild(b.domNode);

        return content;
    }

    var canceled = false;

    toggleGeneric = function(checkboxid, farray, inverted) {

        if(inverted == undefined) inverted = false;

        var box = dijit.byId(checkboxid);
        if(inverted == true) {
            toset = !box.get("value");
        } else{
            toset = box.get("value");
        }
        for(var i=0;i<farray.length;i++) {
            dijit.byId(farray[i]).set('disabled', toset);
        }

    }

    rsyncModeToggle = function() {

        var select = dijit.byId("id_rsync_mode");
        var modname = dijit.byId("id_rsync_remotemodule");
        var path = dijit.byId("id_rsync_remotepath");
        var trm = modname.domNode.parentNode.parentNode;
        var trp = path.domNode.parentNode.parentNode;
        if(select.get('value') == 'ssh') {
            dojo.style(trm, "display", "none");
            dojo.style(trp, "display", "table-row");
        } else {
            dojo.style(trm, "display", "table-row");
            dojo.style(trp, "display", "none");
        }

    }

    setMessage = function(msg, css) {

        if(!css) css = "success";
        var footer = dojo.byId("messages");
        dojo.empty(footer);
        var suc = dojo.create("div");
        dojo.connect(suc, 'onclick', function() {
            dojo.fadeOut({ node: suc }).play();
        });
        footer.appendChild(suc);
        dojo.addClass(suc, css);
        dojo.html.set(suc, "<p>"+msg+"</p>");
        setTimeout(function() { if(suc) dojo.fadeOut({node: suc}).play();}, 7000);

    };

    serviceFailed = function(srv) {
        var obj = dojo.query("img#"+srv+"_toggle");
        if(obj.length > 0) {
            obj = obj[0];
            toggle_service(obj);
        }
    }

    handleJson = function(rnode, data) {

        if(data.type == 'page') {
            rnode.set('content', data.content);
        } else if(data.type == 'form') {

            form = dijit.byId(data.formid);
            dojo.query(".errorlist", form.domNode).forEach(function(item, idx) {
                dojo.destroy(item);
            });
            if(data.error == true) {
                var first = null;
                for(key in data.errors) {

                    //fieldid = data.form_auto_id.replace('%s', key);
                    field = dijit.byId(key);
                    if(!field) continue;
                    if(!first && field.focus)
                        first = field;
                    var ul = dojo.create('ul', {style: {display: "none"}}, field.domNode.parentNode, "first");
                    dojo.attr(ul, "class", "errorlist");
                    for(var i=0; i<data.errors[key].length;i++) {
                        var li = dojo.create('li', {innerHTML: data.errors[key][i]}, ul);
                    }
                    dojo.fx.wipeIn({
                        node: ul,
                        duration: 300
                    }).play();

                }

                if(first) first.focus();

            } else {
                //form.reset();
            }

        }

        if(data.events) {
            for(i=0;i<data.events.length;i++){
                try {
                    eval(data.events[i]);
                } catch(e) {
                    console.log(e);
                }
            }
        }

        if(data.message) {
            setMessage(data.message);
        }

        if(data.error == false && rnode.isInstanceOf(dijit.Dialog)) {
            rnode.hide();
        }

    }

    doSubmit = function(attrs) {

        if(!attrs) {
            attrs = {};
        }

        dojo.query('input[type=button],input[type=submit]', attrs.form.domNode).forEach(
            function(inputElem){
                if(inputElem.type == 'submit') {
                    var dj = dijit.getEnclosingWidget(inputElem);
                    if(dj) {
                        dojo.attr(dj.domNode, "oldlabel", dj.get('label'));
                        dj.set('label', gettext('Please wait...'));
                    }
                }
                dijit.getEnclosingWidget(inputElem).set('disabled',true);
            }
            );

        // prevent the default submit
        dojo.stopEvent(attrs.event);
        var newData = attrs.form.get("value");
        newData['__form_id'] = attrs.form.id;

        var multipart = dojo.query("input[type=file]", attrs.form.domNode).length > 0;

        var rnode = getDialog(attrs.form);
        if(!rnode) rnode = dijit.getEnclosingWidget(attrs.form.domNode.parentNode);

        loadOk = function(data, req) {

            dojo.query('input[type=button],input[type=submit]', attrs.form.domNode).forEach(
                  function(inputElem){
                       dijit.getEnclosingWidget(inputElem).set('disabled',false);
                   }
                );
            var sbtn = dijit.getEnclosingWidget(dojo.query('input[type=submit]', attrs.form.domNode)[0]);
            if(sbtn) {
                if( dojo.hasAttr(sbtn.domNode, "oldlabel")) {
                    sbtn.set('label',dojo.attr(sbtn.domNode, "oldlabel"));
                } else {
                    sbtn.set('label', 'Save');
                }
            }
            handleJson(rnode, data);

            if('onComplete' in attrs) {
                attrs.onComplete(data);
            }

        };

        var handleReq = function(data, ioArgs) {
            var json;
            try {
                json = dojo.fromJson(data);
                if(json.error != true && json.error != false) throw "toJson error";
                loadOk(json, ioArgs);
            } catch(e) {
                console.log(e);
                setMessage(gettext('An error occurred!'), "error");
                try {
                    rnode.hide();
                } catch(e) {
                    rnode.set('content', data);
                }
            }
        };

        if( multipart ) {

            dojo.io.iframe.send({
                url: attrs.url,
                method: 'POST',
                content: {__form_id: attrs.form.id},
                form: attrs.form.id,
                handleAs: 'text',
                handle: handleReq,
            });

        } else {

            dojo.xhrPost({
                url: attrs.url,
                content: newData,
                handleAs: 'text',
                handle: handleReq,
            });

        }

    }


    formSubmit = function(item, e, url, callback, attrs) {
        dojo.stopEvent(e); // prevent the default submit
        if(!attrs) {
            attrs = {};
        }
        var qry = dojo.query('.saved', item.domNode)[0];
        if(qry) dojo.style(qry, 'display', 'none');

        dojo.query('input[type=button],input[type=submit]', item.domNode).forEach(
          function(inputElem){
               if(inputElem.type == 'submit') {
                   var dj = dijit.getEnclosingWidget(inputElem);
                   if(dj) {
                       dojo.attr(dj.domNode, "oldlabel", dj.get('label'));
                       dj.set('label', gettext('Please wait...'));
                   }
               }
               dijit.getEnclosingWidget(inputElem).set('disabled',true);
           }
        );

        var rnode = getDialog(item);
        if(!rnode) rnode = dijit.getEnclosingWidget(item.domNode.parentNode);
        if(!rnode) rnode = dijit.byId("edit_dialog");

        var loadOk = function(data) {

            try {
                var json = dojo.fromJson(data);
                // TODO, workaound for firefox, it does parse html as JSON!!!
                if(json.error != true && json.error != false) {
                    throw "not json"
                }

                try {
                    rnode.hide();
                } catch(err2) {
                    dojo.query('input[type=button],input[type=submit]', item.domNode).forEach(
                      function(inputElem){
                           dijit.getEnclosingWidget(inputElem).set('disabled',false);
                       }
                    );
                    var sbtn = dijit.getEnclosingWidget(dojo.query('input[type=submit]', item.domNode)[0]);
                    if( dojo.hasAttr(sbtn.domNode, "oldlabel")) {
                        sbtn.set('label',dojo.attr(sbtn.domNode, "oldlabel"));
                    } else {
                        sbtn.set('label', 'Save');
                    }
                }
                if(json.error == false){
                    dojo.query('ul[class=errorlist]', rnode.domNode).forEach(function(i) { i.parentNode.removeChild(i); });
                }

                setMessage(json.message);
                if(json.events) {
                    for(i=0;json.events.length>i;i++){
                        try {
                            eval(json.events[i]);
                        } catch (e) {
                            console.log(e);
                        }
                    }
                }
            } catch(err) {

                rnode.set('content', data);
                try {
                    if(callback) callback();
                    var qry = dojo.query('#success', rnode.domNode);
                    if(qry.length>0)
                        dojo.fadeOut({node: rnode, onEnd: function() { rnode.hide(); }}).play();
                } catch(err) {}
            }
        };

        // are there any files to be submited?
        var files = dojo.query("input[type=file]", item.domNode);
        if(files.length > 0) {

            dojo.io.iframe.send({
                url: url + '?iframe=true',
                method: 'POST',
                form: item.domNode,
                handleAs: 'text',
                //headers: {"X-CSRFToken": dojo.cookie('csrftoken')},
                load: loadOk,
	            error: function(response, ioArgs) { },
             });

        } else {

            var newData = item.get("value");
            if (attrs.progressbar == true) {
                rnode.set('content', '<div style="width:300px" data-dojo-props="indeterminate: true" data-dojo-type="dijit.ProgressBar"></div>');
            }
            dojo.xhrPost({
                url: url,
                content: newData,
                handleAs: 'text',
                load: loadOk,
                error: function(data) {

                        setMessage(gettext('An error occurred!'), "error");

                        try {
                           rnode.hide();
                        } catch(err2) {
                            dojo.query('input[type=button],input[type=submit]', item.domNode).forEach(
                              function(inputElem){
                                   dijit.getEnclosingWidget(inputElem).set('disabled',false);
                               }
                            );

                            dijit.getEnclosingWidget(dojo.query('input[type=submit]', item.domNode)[0]).set('label','Save');
                        }
                 }
             });

         }

    }

    checkNumLog = function(unselected) {
        var num = 0;
        for(var i=0;i<unselected.length;i++) {
            var q = dojo.query("input[name=zpool_"+unselected[i]+"]:checked");
            if(q.length > 0) {
                if(q[0].value == 'log')
                num += 1;
            }
        }
        if(num == 1) {
            dojo.style("lowlog", "display", "");
        } else {
            dojo.style("lowlog", "display", "none");
        }
    }

    taskrepeat_checkings = function() {

        var repeat = dijit.byId("id_task_repeat_unit");
        wk = dojo.query(dijit.byId('id_task_byweekday_0').domNode).parents("tr").first()[0];
        if(repeat.get('value') != 'weekly') {
            dojo.style(wk, "display", "none");
        } else {
            dojo.style(wk, "display", "");
        }

    }

    wizardcheckings = function(vol_change, first_load) {

        if(!dijit.byId("wizarddisks")) return;
        var disks = dijit.byId("wizarddisks");
        var d = disks.get('value');
        dojo.html.set(dojo.byId("wizard_num_disks"), d.length + '');

        var zfs = dojo.query("input[name=volume_fstype]")[1].checked;

        if(vol_change == true) {
            var unselected = [];
            disks.invertSelection(null);
            var opts = disks.get("value");
            for(var i=0;i<opts.length;i++) {
                unselected.push(opts[i]);
            }
            disks.invertSelection(null);

            if(unselected.length > 0 && zfs == true && first_load != true) {

                var tab = dojo.byId("disks_unselected");
                dojo.query("#disks_unselected tbody tr").orphan();
                var txt = "";
                var toappend = [];
                for(var i=0;i<unselected.length;i++) {
                    var tr = dojo.create("tr");
                    var td = dojo.create("td", {innerHTML: unselected[i]});
                    tr.appendChild(td);

                    var td = dojo.create("td");
                    var rad = new dijit.form.RadioButton({ checked: true, value: "none", name: "zpool_"+unselected[i]});
                    dojo.connect(rad, 'onClick', function() {checkNumLog(unselected);});
                    td.appendChild(rad.domNode);
                    tr.appendChild(td);

                    var td = dojo.create("td");
                    var rad = new dijit.form.RadioButton({ value: "log", name: "zpool_"+unselected[i]});
                    dojo.connect(rad, 'onClick', function() {checkNumLog(unselected);});
                    td.appendChild(rad.domNode);
                    tr.appendChild(td);

                    var td = dojo.create("td");
                    var rad = new dijit.form.RadioButton({ value: "cache", name: "zpool_"+unselected[i]});
                    dojo.connect(rad, 'onClick', function() {checkNumLog(unselected);});
                    td.appendChild(rad.domNode);
                    tr.appendChild(td);

                    var td = dojo.create("td");
                    var rad = new dijit.form.RadioButton({ value: "spare", name: "zpool_"+unselected[i]});
                    dojo.connect(rad, 'onClick', function() {checkNumLog(unselected);});
                    td.appendChild(rad.domNode);
                    tr.appendChild(td);

                    toappend.push(tr);
                }

                for(var i=0;i<toappend.length;i++) {
                    dojo.place(toappend[i], dojo.query("#disks_unselected tbody")[0]);
                }

               dojo.style("zfsextra", "display", "");

            } else {
                if(zfs == true && first_load == true) {
                    dojo.style("zfsextra", "display", "");
                } else {
                    dojo.query("#disks_unselected tbody tr").orphan();
                    dojo.style("zfsextra", "display", "none");
                }
            }
        } else if(zfs == false) {
               dojo.style("zfsextra", "display", "none");
        }

        var ufs = dojo.query("#fsopt input")[0].checked;
        var zfs = dojo.query("#fsopt input")[1].checked;
        if(d.length >= 2) {
            dojo.style("grpopt", "display", "");
        } else {
            dojo.style("grpopt", "display", "none");
            dojo.query("input[name=group_type]:checked").forEach(function(tag) { dijit.getEnclosingWidget(tag).set('checked', false);  });
        }

        if(zfs) {
            dojo.style('zfssectorsize', 'display', 'table-row');
        } else {
            dojo.style('zfssectorsize', 'display', 'none');
        }

        if(ufs) {
            dojo.style("ufspath", "display", "table-row");
            dojo.style("ufspathen", "display", "table-row");
        } else {
            dojo.style("ufspath", "display", "none");
            dojo.style("ufspathen", "display", "none");
        }

        if(d.length >= 3 && zfs) {
                dojo.style("grpraidz", "display", "block");
        } else {
                dojo.style("grpraidz", "display", "none");
        }

        if(d.length >= 4 && zfs) {
                dojo.style("grpraidz2", "display", "block");
        } else {
                dojo.style("grpraidz2", "display", "none");
        }

        if(ufs && d.length-1 >= 2 && (((d.length-2)&(d.length-1)) == 0)) {
            if(ufs)
                dojo.style("grpraid3", "display", "block");
        } else {
            dojo.style("grpraid3", "display", "none");
        }
    }

    getDialog = function(from) {

        var turn = from;
        while(1) {
            turn = dijit.getEnclosingWidget(turn.domNode.parentNode);
            if(turn == null) return null;
            if(turn.isInstanceOf(dijit.Dialog)) break;
        }
        return turn;

    };

    getForm = function(from) {

        var turn = from;
        while(1) {
            turn = dijit.getEnclosingWidget(turn.domNode.parentNode);
            if(turn.isInstanceOf(dijit.form.Form)) break;
        }
        return turn;

    };

    cancelDialog = function(from) {

        var dialog = getDialog(from);
        canceled = true;
        dialog.hide();

    };

    refreshTabs = function(nodes) {
        if(nodes && canceled == false) {
            var fadeArgs = {
               node: "fntree",
               onEnd: function() { dijit.byId("fntree").reload(); }
             };
            dojo.fadeOut(fadeArgs).play();
            dojo.forEach(nodes, function(entry, i) {
                if(entry.isInstanceOf(dijit.layout.ContentPane)) {
                    entry.refresh();
                    var par = dijit.getEnclosingWidget(entry.domNode.parentNode);
                    par.selectChild(entry);
                    var par2 = dijit.getEnclosingWidget(par.domNode.parentNode);
                    if(par2 && par2.isInstanceOf(dijit.layout.ContentPane))
                        dijit.byId("content").selectChild(par2);
                } else {
                    var par = dojo.query(entry.domNode).parents(".objrefresh").first()[0];
                    var cp = dijit.getEnclosingWidget(par);
                    if(cp) cp.refresh();
                }
            });

        }
    }

    __stack = [];
    addToStack = function(f) {
        __stack.push(f);
    }

    processStack = function() {

        while(__stack.length > 0) {
            f = __stack.pop();
            try {
                f();
            } catch(e) {
                console.log(e);
            }
        }

    }

    commonDialog = function(attrs) {
        canceled = false;
        dialog = new dijit.Dialog({
            id: attrs.id,
            title: attrs.name,
            href: attrs.url,
            parseOnLoad: true,
            closable: true,
            style: attrs.style,
            onHide: function() {
                setTimeout(dojo.hitch(this, 'destroyRecursive'), dijit.defaultDuration);
                refreshTabs(attrs.nodes);
            },
            onLoad: function() {
                processStack();
                this.layout();
            }
        });
        if(attrs.onLoad) {
            f = dojo.hitch(dialog, attrs.onLoad);
            f();
        }
        dialog.show();
    };

    addObject = function(name, url, nodes) {
        commonDialog({
            id: "add_dialog",
            style: "max-width: 75%;max-height:70%;background-color:white;overflow:auto;",
            name: name,
            url: url,
            nodes: nodes
            });
    };

    editObject = function(name, url, nodes, onload) {
        commonDialog({
            id: "edit_dialog",
            style: "max-width: 75%;max-height:70%;background-color:white;overflow:auto;",
            name: name,
            url: url,
            nodes: nodes,
            onLoad: onload
            });
    }


    editScaryObject = function(name, url, nodes) {
        commonDialog({
            id: "editscary_dialog",
            style: "max-width: 75%;max-height:70%;background-color:white;overflow:auto;",
            name: name,
            url: url,nodes: nodes
            });
    };

    volumeWizard = function(name, url, nodes) {
        commonDialog({
            id: "wizard_dialog",
            style: "max-width: 650px;min-height:200px;max-height:500px;background-color:white;overflow:auto;",
            name: name,
            url: url,
            nodes: nodes
            });
    }

    viewModel = function(name, url) {
        var p = dijit.byId("content");
        var c = p.getChildren();
        for(var i=0; i<c.length; i++){
            if(c[i].title == name){
                c[i].href = url;
                p.selectChild(c[i]);
                return;
            }
        }
        var pane = new dijit.layout.ContentPane({
            href: url,
            title: name,
            closable: true,
            parseOnLoad: true,
            refreshOnShow: true,
        });
        dojo.addClass(pane.domNode, "objrefresh" );
        p.addChild(pane);
        p.selectChild(pane);
    }

    refreshImgs = function() {

        dojo.query(".chart > img").forEach(function(e) {
            e.src = new String(e.src).split('?')[0] + '?' + new Date().getTime();
        });
        setTimeout(refreshImgs, 300000);
    }

    require([
        "dojo",
        "dojo/ready",
        "dojo/_base/xhr",
        "dojo/_base/html",
        "dojo/cookie",
        "dojo/data/ItemFileReadStore",
        "dojo/io/iframe",
        "dojo/parser",
        "dojo/NodeList-traverse",
        "dojo/NodeList-manipulate",
        "dojo/fx",
        "dijit/_base/manager",
        "dijit/form/CheckBox",
        "dijit/form/FilteringSelect",
        "dijit/form/Form",
        "dijit/form/MultiSelect",
        "dijit/form/NumberTextBox",
        "dijit/form/Select",
        "dijit/form/Textarea",
        "dijit/form/RadioButton",
        "dijit/form/TimeTextBox",
        "dijit/form/ValidationTextBox",
        "dijit/layout/BorderContainer",
        "dijit/layout/ContentPane",
        "dijit/layout/TabContainer",
        "dijit/tree/ForestStoreModel",
        "dijit/Dialog",
        "dijit/MenuBar",
        "dijit/MenuBarItem",
        "dijit/ProgressBar",
        "dijit/Tooltip",
        "dojox/data/JsonRestStore",
        "dojox/fx/scroll",
        "dojox/grid/EnhancedGrid",
        "dojox/grid/enhanced/plugins/DnD",
        "dojox/grid/enhanced/plugins/Menu",
        "dojox/grid/enhanced/plugins/NestedSorting",
        "dojox/grid/enhanced/plugins/IndirectSelection",
        "dojox/grid/enhanced/plugins/Pagination",
        "dojox/grid/enhanced/plugins/Filter",
        "dojox/grid/TreeGrid",
        "dojox/validate",
        ], function(dojo, ready, xhr, JsonRestStore, cookie, html, dmanager, FSM, parser) {

        dojo.registerModulePath("freeadmin", "../../../../../media/lib/js/freeadmin");

        dojo._contentHandlers.text = (function(old){
          return function(xhr){
            if(xhr.responseText.match("<!-- THIS IS A LOGIN WEBPAGE -->")){
              window.location='/';
              return '';
            }
            var text = old(xhr);
            return text;
          }
        })(dojo._contentHandlers.text);

        var originalXHR = dojo.xhr;
        dojo.xhr = function(httpVerb, xhrArgs, hasHTTPBody) {
          if(!xhrArgs.headers) xhrArgs.headers = {};
          xhrArgs.headers["X-CSRFToken"] = dojo.cookie('csrftoken');
          return originalXHR(httpVerb, xhrArgs, hasHTTPBody);
        }

        ready(function() {
            setTimeout(refreshImgs, 300000);

            var store = new dojox.data.JsonRestStore({
                target: "/admin/menu.json",
                labelAttribute: "name",
            });

            var treeModel = new dijit.tree.ForestStoreModel({
                store: store,
                query: {},
                rootId: "root",
                rootLabel: "FreeNAS",
                childrenAttrs: ["children"]
            });

            var geticons = function(item,opened) {
                if(item.icon) return item.icon;
                return (!item || this.model.mayHaveChildren(item)) ? (opened ? "dijitFolderOpened" : "dijitFolderClosed") : "dijitLeaf";
            };

            var treeclick = function(item) {
                var p = dijit.byId("content");

                if(item.type == 'object' ||
                   item.type == 'dialog' ||
                   item.type == 'editobject' ||
                   item.type == 'volumewizard'
                    ) {
                    var data = dojo.query(".data_"+item.app_name+"_"+item.model);
                    var func;
                    if(item.type == 'volumewizard') func = volumeWizard;
                    else func = editObject;
                    if(data) {
                        widgets = [];
                        data.forEach(function(item, idx) {
                            widget = dijit.getEnclosingWidget(item);
                            if(widget) {
                                widgets.push(widget);
                            }
                        });
                        func(item.name, item.url, widgets);
                    } else
                        func(item.name, item.url);
                } else if(item.type == 'opennetwork') {
                    Menu.openNetwork(item.gname);
                } else if(item.type == 'en_dis_services') {
                    Menu.openServices();
                } else if(item.type == 'en_dis_plugins') {
                    Menu.openPlugins();
                } else if(item.type == 'pluginsfcgi') {
                    Menu.openPluginsFcgi(p, item);
                } else if(item.type == 'openaccount') {
                    Menu.openAccount(item.gname);
                } else if(item.type == 'iscsi') {
                    Menu.openISCSI(item.gname);
                } else if(item.type == 'logout') {
                    window.location='/account/logout/';
                } else if(item.action == 'displayprocs') {
                    dijit.byId("top_dialog").show();
                } else if(item.action == 'shell') {
                    dijit.byId("shell_dialog").show();
                } else if(item.action == 'reboot') {
                    dijit.byId("rebootDialog").show();
                } else if(item.action == 'shutdown') {
                    dijit.byId("shutdownDialog").show();
                } else if(item.type == 'opensharing') {
                    Menu.openSharing(item.gname);
                } else if(item.type == 'openstorage') {
                    Menu.openStorage(item.gname);
                } else if(item.type == 'opencron') {
                    Menu.openCron();
                } else if(item.type == 'viewmodel') {
                    //  get the children and make sure we haven't opened this yet.
                    var c = p.getChildren();
                    for(var i=0; i<c.length; i++){
                        if(c[i].title == item.name){
                            p.selectChild(c[i]);
                            return;
                        }
                    }
                    var pane = new dijit.layout.ContentPane({
                        id: "data_"+item.app_name+"_"+item.model,
                        href: item.url,
                        title: item.name,
                        closable: true,
                        refreshOnShow: true,
                        parseOnLoad: true,
                    });
                    p.addChild(pane);
                    dojo.addClass(pane.domNode, ["objrefresh","data_"+item.app_name+"_"+item.model] );
                    p.selectChild(pane);
                } else {
                    //  get the children and make sure we haven't opened this yet.
                    var c = p.getChildren();
                    for(var i=0; i<c.length; i++){
                        if(c[i].tab == item.gname){
                            p.selectChild(c[i]);
                            return;
                        }
                    }
                    var pane = new dijit.layout.ContentPane({
                        href: item.url,
                        title: item.name,
                        closable: true,
                        parseOnLoad: true,
                    });
                    pane.tab = item.gname;
                    dojo.addClass(pane.domNode, ["objrefresh","data_"+item.app_name+"_"+item.model] );
                    p.addChild(pane);
                    p.selectChild(pane);
                }

            };

            require([
                "freeadmin/tree/Tree",
                "freeadmin/ESCDialog",
                "freeadmin/tree/TreeLazy",
                "freeadmin/tree/JsonRestStore",
                "freeadmin/tree/ForestStoreModel",
                "freeadmin/form/Cron",
                ], function(Tree, ESCDialog) {
                mytree = new freeadmin.tree.Tree({
                    id: "fntree",
                    model: treeModel,
                    showRoot: false,
                    onClick: treeclick,
                    onLoad: function() {
                        var fadeArgs = {
                           node: "fntree",
                         };
                        dojo.fadeIn(fadeArgs).play();
                    },
                    openOnClick: true,
                    getIconClass: geticons,
                }
                );
                dijit.byId("menupane").set('content', mytree);

                var shell = new ESCDialog({
                    id: "shell_dialog",
                    content: '<pre class="ix" tabindex="1" id="shell_output">Loading...</pre>',
                    style: "min-height:400px;background-color: black;",
                    onShow: function() {

                        function handler(msg,value) {
                            switch(msg) {
                            case 'conn':
                                //startMsgAnim('Tap for keyboard',800,false);
                                break;
                            case 'disc':
                                //startMsgAnim('Disconnected',0,true);
                                _webshell = undefined;
                                dijit.byId("shell_dialog").hide();
                                break;
                            case 'curs':
                                cy=value;
                                //scroll(cy);
                                break;
                            }
                        }

                        try {
                            _webshell.islocked=false;
                            _webshell.update();
                        } catch(e) {
                            _webshell=new webshell("shell_output", 80, 24, handler);
                        }
                        document.onkeypress=_webshell.keypress;
                        document.onkeydown=_webshell.keydown;

                    },
                    onHide: function(e) {
                        if(_webshell)
                            _webshell.islocked=true;
                        document.onkeypress=null;
                        document.onkeydown=null;
                    }
                });
                shell.placeAt("shell_dialog_holder");

            });

        });
    });
