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

    dojo.require("dojo.data.ItemFileReadStore");
    dojo.require("dojo.data.ItemFileWriteStore");
    dojo.require("dojo.dnd.Moveable");
    //dojo.require("dijit.tree.dndSource");
    dojo.require("dojo.NodeList-traverse");
    dojo.require("dojo.NodeList-manipulate");
    dojo.require("dojo.io.iframe");
    dojo.require("dojo._base.xhr");
    dojo.require("dojox.validate.regexp");
    dojo.require("dojox.form.FileInput");
    dojo.require("dojox.form.CheckedMultiSelect");
    dojo.require("dojox.grid.DataGrid");
    dojo.require("dojox.data.JsonRestStore");
    dojo.require("dojox.data.FileStore");
    dojo.require("dojox.string.sprintf");
    dojo.require("dijit.Tree");
    dojo.require("dijit.layout.BorderContainer");
    dojo.require("dijit.layout.ContentPane");
    dojo.require("dijit.layout.TabContainer");
    dojo.require("dijit.form.MultiSelect");
    dojo.require("dijit.ProgressBar");
    dojo.require("dijit.MenuBar");
    dojo.require("dijit.MenuBarItem");
    dojo.require("dijit.Dialog");
    dojo.require("dijit.form.Form");
    dojo.require("dijit.form.Button");
    dojo.require("dijit.form.Select");
    dojo.require("dijit.form.ValidationTextBox");
    dojo.require("dijit.form.NumberTextBox");
    dojo.require("dijit.form.Textarea");
    dojo.require("dijit.form.TimeTextBox");
    dojo.require("dijit.form.ComboBox");
    dojo.require("dijit.form.FilteringSelect");
    dojo.require("dijit.form.NumberTextBox");
    dojo.require("dijit.form.HorizontalSlider");
    dojo.require("dijit.form.HorizontalRule");
    dojo.require("dijit.form.HorizontalRuleLabels");

    dojo.require("dojox.data.JsonRestStore");
    dojo.require("dojox.grid.EnhancedGrid");
    dojo.require("dojox.grid.enhanced.plugins.DnD");
    dojo.require("dojox.grid.enhanced.plugins.Menu");
    dojo.require("dojox.grid.enhanced.plugins.NestedSorting");
    dojo.require("dojox.grid.enhanced.plugins.IndirectSelection");
    dojo.require("dojox.grid.enhanced.plugins.Pagination");

    dojo.registerModulePath("freeadmin", "../../../../../media/lib/js/freeadmin");
    dojo.require("freeadmin.form.Cron");
    dojo.require("freeadmin.tree.Tree");
    dojo.require("freeadmin.tree.TreeLazy");

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
        openServices: function() {
            var opened = false;
            var p = dijit.byId("content");

            var c = p.getChildren();
            for(var i=0; i<c.length; i++){
                if(c[i].tab == 'services'){
                    p.selectChild(c[i]);
                    opened = true;
                }
            }
            if(opened != true) {
                var pane = new dijit.layout.ContentPane({
                    title: gettext('Services'),
                    closable: true,
                    href: this.urlServices,
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

    addAlias = function(a, name) {

        extra = dijit.byId("id_"+name+"-TOTAL_FORMS");
        var extran = extra.get("value");
        n4a = new dijit.form.TextBox({
            name: name+"-"+extran+"-alias_v4address",
            value: "",
        });

        getid4 = dijit.byId("id_"+name+"-"+(parseInt(extran)-1)+"-alias_v4netmaskbit");
        n4n = new dijit.form.Select({
            name: name+"-"+extran+"-alias_v4netmaskbit",
            value: "",
            options: getid4.options,
        });

        n6a = new dijit.form.TextBox({
            name: name+"-"+extran+"-alias_v6address",
            value: "",
        });

        getid6 = dijit.byId("id_"+name+"-"+(parseInt(extran)-1)+"-alias_v6netmaskbit");
        n6n = new dijit.form.Select({
            name: name+"-"+extran+"-alias_v6netmaskbit",
            value: "",
            options: getid6.options,
        });

        ni = new dijit.form.TextBox({
            name: name+"-"+extran+"-id",
            type: "hidden",
        });
        var tr = dojo.create("tr");
        var td1 = dojo.create("th", {innerHTML: "IPv4 Address"}, tr, "last");
        var td2 = dojo.create("td", null, tr, "last");
        dojo.query(a.parentNode.parentNode).before(tr);
        n4a.placeAt(td2);
        ni.placeAt(td2);

        var tr = dojo.create("tr");
        var td1 = dojo.create("th", {innerHTML: "IPv4 Netmask"}, tr, "last");
        var td2 = dojo.create("td", null, tr, "last");
        dojo.query(a.parentNode.parentNode).before(tr);
        n4n.placeAt(td2);

        var tr = dojo.create("tr");
        var td1 = dojo.create("th", {innerHTML: "IPv6 Address"}, tr, "last");
        var td2 = dojo.create("td", null, tr, "last");
        dojo.query(a.parentNode.parentNode).before(tr);
        n6a.placeAt(td2);

        ni.placeAt(td2);

        var tr = dojo.create("tr");
        var td1 = dojo.create("th", {innerHTML: "IPv6 Netmask"}, tr, "last");
        var td2 = dojo.create("td", null, tr, "last");
        dojo.query(a.parentNode.parentNode).before(tr);
        n6n.placeAt(td2);

        extra.set('value', parseInt(extran) + 1);
    }

    function toggle_service(obj) {
        var td = obj.parentNode;
        var n = dojo.create("div", {  }, td);
        dojo.addClass(n, "dijitContentPaneLoading");
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

    function buttongrid(v) {
        var json = dojo.fromJson(v);
        dojo.parser.parse(dojo.byId(this.id));
        var gridhtml = dijit.getEnclosingWidget(dojo.byId(this.id));

        var content = new dijit.layout.ContentPane({});
        var b = new dijit.form.Button({label: gettext("Edit")});

        dojo.connect(b.domNode, 'onclick', function(){ editObject(gettext('Edit Disk'), json.edit_url, [gridhtml,]); });
        content.domNode.appendChild(b.domNode);

        if(json.replace_url) {
            var b2 = new dijit.form.Button({label: gettext("Replace")});
            dojo.connect(b2.domNode, 'onclick', function(){ editObject(gettext('Disk Replacement'), json.replace_url, [gridhtml,]); });
            content.domNode.appendChild(b2.domNode);
        }
        if(json.detach_url) {
            var b3 = new dijit.form.Button({label: gettext("Detach")});
            dojo.connect(b3.domNode, 'onclick', function(){ editObject(gettext('Disk Detach'), json.detach_url, [gridhtml,]); });
            content.domNode.appendChild(b3.domNode);
        }

        return content;
    }

    var canceled = false;

    toggleLuc = function(c) {

        var toset;
        var box = dijit.byId("id_iscsi_toggleluc");
        if(box.get("value")==false) {
            toset = true;
        } else{
            toset = false;
        }
        dijit.byId("id_iscsi_lucip").set('disabled', toset);
        dijit.byId("id_iscsi_lucport").set("disabled", toset);
        dijit.byId("id_iscsi_luc_authnetwork").set("disabled", toset);
        dijit.byId("id_iscsi_luc_authmethod").set("disabled", toset);
        dijit.byId("id_iscsi_luc_authgroup").set("disabled", toset);

    }

    toggleEmail = function(c) {

        var toset;
        var box = dijit.byId("id_em_smtp");
        if(box.get("value")==false) {
            toset = true;
        } else{
            toset = false;
        }
        dijit.byId("id_em_pass1").set('disabled', toset);
        dijit.byId("id_em_pass2").set("disabled", toset);
        dijit.byId("id_em_user").set("disabled", toset);

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

    formSubmit = function(item, e, url, callback, attrs) {
        dojo.stopEvent(e); // prevent the default submit
        if(!attrs) {
            attrs = {};
        }
        var qry = dojo.query('.saved', item.domNode)[0];
        if(qry) dojo.style(qry, 'display', 'none');

        dojo.query('input[type=button],input[type=submit]', item.domNode).forEach(
          function(inputElem){
               dijit.getEnclosingWidget(inputElem).set('disabled',true);
           }
        );

        var rnode = dijit.getEnclosingWidget(item.domNode.parentNode);
        if(!rnode) rnode = dijit.byId("edit_dialog");

        // are there any files to be submited?
        var files = dojo.query("input[type=file]", item.domNode);
        if(files.length > 0) {

            dojo.io.iframe.send( {
                url: url + '?iframe=true',
                method: 'POST',
                form: item.domNode,
                handleAs: 'text',
                //headers: {"X-CSRFToken": dojo.cookie('csrftoken')},
                load: function(data, ioArgs) {

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
                            dijit.getEnclosingWidget(dojo.query('input[type=submit]', item.domNode)[0]).set('label','Save');
                        }

                        if(json.error == false){
                            dojo.query('ul[class=errorlist]', rnode.domNode).forEach(function(i) { i.parentNode.removeChild(i); });
                        }

                        setMessage(json.message);

                        //dojo.style(suc, "opacity", "0");
                        //dojo.fadeIn({ node: suc }).play();
                    } catch(err) {
                        rnode.set('content', data);
                        if(callback) callback();
                        var qry = dojo.query('#success', rnode.domNode);
                        if(qry.length>0)
                            dojo.fadeOut({node: rnode, onEnd: function() { rnode.hide(); }}).play();
                    }

                },
	        error: function(response, ioArgs) { },
             });

        } else {

            var newData = item.get("value");
            if (attrs.progressbar == true) {
                rnode.set('content', '<div style="width:300px" indeterminate="true" dojoType="dijit.ProgressBar"></div>');
            }
            dojo.xhrPost( {
                url: url,
                content: newData,
                handleAs: 'text',
                load: function(data) {

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
                            dijit.getEnclosingWidget(dojo.query('input[type=submit]', item.domNode)[0]).set('label','Save');
                        }
                        if(json.error == false){
                            dojo.query('ul[class=errorlist]', rnode.domNode).forEach(function(i) { i.parentNode.removeChild(i); });
                        }

                        setMessage(json.message);
                        //dojo.style(suc, "opacity", "0");
                        //dojo.fadeIn({ node: suc }).play();
                        if(json.events) {
                            for(i=0;json.events.length>i;i++){
                                eval(json.events[i]);
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
                },
                error: function(data) {

                        setMessage(gettext('Some error ocurred!'), "error");

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

    function checkNumLog(unselected) {
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
        //var d = disks.getSelected();
        var d = disks.get('value');

        var zfs = dojo.query("input[name=volume_fstype]")[1].checked;

        if(vol_change == true) {
            var unselected = [];
            var opts = disks.getOptions();
            for(var i=0;i<opts.length;i++) {

                var selected = false;
                for(var j=0;j<d.length;j++) {
                    if (opts[i].value == d[j]) {
                        selected = true;
                    }
                }
                if(selected == false) {
                    unselected.push(opts[i].value);
                }

            }

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
        } else {
            dojo.style("ufspath", "display", "none");
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

    addObject = function(name, url, nodes) {
        canceled = false;
        dialog = new dijit.Dialog({
            id: 'add_dialog',
            title: name,
            href: url,
            parseOnLoad: true,
            closable: true,
            style: "max-width: 75%;max-height:70%;background-color:white;overflow:auto;",
            onHide: function() {
                setTimeout(dojo.hitch(this, 'destroyRecursive'), dijit.defaultDuration);
                refreshTabs(nodes);
            },
        });
        dialog.show();
    };

    refreshTabs = function(nodes) {
        if(nodes && canceled == false) {
            var fadeArgs = {
               node: "mytree",
               onEnd: function() { dijit.byId("mytree").reload(); }
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

    editObject = function(name, url, nodes, onload) {
        canceled = false;
        dialog = new dijit.Dialog({
            id: 'edit_dialog',
            title: name,
            href: url,
            parseOnLoad: true,
            closable: true,
            style: "max-width: 75%;max-height:70%;background-color:white;overflow:auto;",
            onHide: function() {
                setTimeout(dojo.hitch(this, 'destroyRecursive'), dijit.defaultDuration);
                refreshTabs(nodes);
            },
        });
        if(onload) {
            f = dojo.hitch(dialog, onload);
            f();
        }
        dialog.show();
    };

    //FIXME: Duplicated of editObject changing ID
    editScaryObject = function(name, url, nodes) {
        canceled = false;
        dialog = new dijit.Dialog({
            id: 'editscary_dialog',
            title: name,
            href: url,
            parseOnLoad: true,
            closable: true,
            style: "max-width: 75%;max-height:70%;background-color:white;overflow:auto;",
            onHide: function() {
                setTimeout(dojo.hitch(this, 'destroyRecursive'), dijit.defaultDuration);
                refreshTabs(nodes);
            },
        });
        dialog.show();
    };

    volumeWizard = function(name, url, nodes) {
         dialog = new dijit.Dialog({
             id: 'wizard_dialog',
             title: name,
             href: url,
             parseOnLoad: true,
             closable: true,
             style: "max-width: 650px;min-height:200px;max-height:500px;background-color:white;overflow:auto;",
             onHide: function() {
                setTimeout(dojo.hitch(this, 'destroyRecursive'), dijit.defaultDuration);
                refreshTabs(nodes);
             },
         });
         dialog.show();
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

    dojo.addOnLoad(function() {

        setTimeout(refreshImgs, 300000);

        var store = new dojo.data.ItemFileReadStore({
            url: "/admin/menu.json",
            urlPreventCache: true,
            clearOnClose: true,
        });

        var treeModel = new dijit.tree.ForestStoreModel({
            store: store,
            query: {
                "type": "app"
            },
            rootId: "root",
            rootLabel: "FreeNAS",
            childrenAttrs: ["children"]
        });

        geticons = function(item,opened) {
            if(item.icon) return item.icon;
            return (!item || this.model.mayHaveChildren(item)) ? (opened ? "dijitFolderOpened" : "dijitFolderClosed") : "dijitLeaf";
        };

        treeclick = function(item) {
            var p = dijit.byId("content");

            if(item.type && item.type == 'object') {
                var data = dojo.query(".data_"+item.app_name+"_"+item.model);
                if(data) {
                    widgets = [];
                    data.forEach(function(item, idx) {
                        widget = dijit.getEnclosingWidget(item);
                        if(widget) {
                            widgets.push(widget);
                        }
                    });
                    addObject(item.name, item.view, widgets);
                } else
                    addObject(item.name, item.view);
            } else if(item.type && item.type == 'volumewizard') {
                var data = dojo.query(".data_"+item.app_name+"_"+item.model);
                if(data) {
                    widgets = [];
                    data.forEach(function(item, idx) {
                        widget = dijit.getEnclosingWidget(item);
                        if(widget) {
                            widgets.push(widget);
                        }
                    });
                    volumeWizard(item.name, item.view, widgets);
                } else
                    volumeWizard(item.name, item.view);
            } else if(item.type && item.type == 'editobject') {
                var data = dojo.query(".data_"+item.app_name+"_"+item.model);
                if(data) {
                    widgets = [];
                    data.forEach(function(item, idx) {
                        widget = dijit.getEnclosingWidget(item);
                        if(widget) {
                            widgets.push(widget);
                        }
                    });
                    editObject(item.name, item.view, widgets);
                } else
                    editObject(item.name, item.view);
            } else if(item.type && item.type == 'opennetwork') {
                Menu.openNetwork(item.gname);
            } else if(item.type && item.type == 'en_dis_services') {
                Menu.openServices();
            } else if(item.type && item.type == 'openaccount') {
                Menu.openAccount(item.gname);
            } else if(item.type && item.type == 'iscsi') {
                Menu.openISCSI(item.gname);
            } else if(item.type && item.type == 'logout') {
                window.location='/account/logout/';
            } else if(item.action && item.action == 'displayprocs') {
                    dijit.byId("top_dialog").show();
            } else if(item.action && item.action == 'reboot') {
                    dijit.byId("rebootDialog").show();
            } else if(item.action && item.action == 'shutdown') {
                    dijit.byId("shutdownDialog").show();
            } else if(item.type && item.type == 'opensharing') {
                Menu.openSharing(item.gname);
            } else if(item.type && item.type == 'openstorage') {
                Menu.openStorage(item.gname);
            } else if(item.type && item.type == 'opencron') {
                Menu.openCron();
            } else if(item.type && item.type == 'viewmodel') {
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
                    href: item.view,
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
                    href: item.view,
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

        mytree = new freeadmin.tree.Tree({
            id: "mytree",
            model: treeModel,
            showRoot: false,
            onClick: treeclick,
            onLoad: function() {
                var fadeArgs = {
                   node: "mytree",
                 };
                dojo.fadeIn(fadeArgs).play();
            },
            openOnClick: true,
            getIconClass: geticons,
        }
        );
        dijit.byId("menupane").set('content', mytree);

    });
