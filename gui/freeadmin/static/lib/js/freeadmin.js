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

require([
    "dojo",
    "dojo/_base/array",
    "dojo/_base/connect",
    "dojo/_base/event",
    "dojo/_base/fx",
    "dojo/_base/lang",
    "dojo/_base/window",
    "dojo/cookie",
    "dojo/data/ItemFileReadStore",
    "dojo/dom",
    "dojo/dom-attr",
    "dojo/dom-class",
    "dojo/dom-construct",
    "dojo/dom-style",
    "dojo/fx",
    "dojo/html",
    "dojo/json",
    "dojo/on",
    "dojo/parser",
    "dojo/query",
    "dojo/ready",
    "dojo/request/iframe",
    "dojo/request/xhr",
    "dojo/rpc/JsonService",
    "dojo/NodeList-traverse",
    "dojo/NodeList-manipulate",
    "freeadmin/tree/Tree",
    "freeadmin/ESCDialog",
    "freeadmin/Menu",
    "freeadmin/WebShell",
    "freeadmin/RRDControl",
    "freeadmin/tree/TreeLazy",
    "freeadmin/tree/JsonRestStore",
    "freeadmin/tree/ForestStoreModel",
    "freeadmin/form/Cron",
    "freeadmin/form/PathSelector",
    "freeadmin/form/UnixPerm",
    "dijit/_base/manager",
    "dijit/form/Button",
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
    "dijit/registry",
    "dijit/tree/ForestStoreModel",
    "dijit/Dialog",
    "dijit/MenuBar",
    "dijit/MenuBarItem",
    "dijit/ProgressBar",
    "dijit/Tooltip",
    "dojox/form/BusyButton",
    "dojox/grid/EnhancedGrid",
    "dojox/grid/enhanced/plugins/DnD",
    "dojox/grid/enhanced/plugins/Menu",
    "dojox/grid/enhanced/plugins/NestedSorting",
    "dojox/grid/enhanced/plugins/IndirectSelection",
    "dojox/grid/enhanced/plugins/Pagination",
    "dojox/grid/enhanced/plugins/Filter",
    "dojox/grid/TreeGrid",
    "dojox/uuid/_base",
    "dojox/uuid/generateRandomUuid",
    "dojox/validate"
    ], function(
    dojo,
    dArray,
    dConnect,
    dEvent,
    dFx,
    lang,
    dWindow,
    cookie,
    ItemFileReadStore,
    dom,
    domAttr,
    domClass,
    domConstruct,
    domStyle,
    fx,
    html,
    JSON,
    on,
    parser,
    query,
    ready,
    iframe,
    xhr,
    JsonService,
    NodeListTraverse,
    NodeListManipulate,
    Tree,
    ESCDialog,
    fMenu,
    WebShell,
    RRDControl,
    TreeLazy,
    JsonRestStore,
    ForestStoreModel,
    Cron,
    PathSelector,
    UnixPerm,
    manager,
    Button,
    CheckBox,
    FilteringSelect,
    Form,
    MultiSelect,
    NumberTextBox,
    Select,
    Textarea,
    RadioButton,
    TimeTextBox,
    ValidationTextBox,
    BorderContainer,
    ContentPane,
    TabContainer,
    registry,
    ForestStoreModel,
    Dialog,
    MenuBar,
    MenuBarItem,
    ProgressBar,
    Tooltip,
    BusyButton,
    EnhancedGrid,
    enhancedDnD,
    enhancedMenu,
    enhancedNestedSorting,
    enhancedIndirectSelection,
    enhancedPagination,
    enhancedFilter,
    TreeGrid,
    uuidBase,
    generateRandomUuid,
    dojoxvalidate
    ) {

    Menu = new fMenu();

    restartHttpd = function(newurl) {

        var handle = function(data) {
            if(newurl) {
                setTimeout(function () {
                    dWindow.location = newurl;
                }, 1500);
            }
        };

        xhr.get('/system/restart-httpd/', {
            sync: true
        }).then(handle, handle);

    }

    reloadHttpd = function(newurl) {

        var handle = function(data) {
            if(newurl) {
                setTimeout(function () {
                    dWindow.location = newurl;
                }, 1500);
            }
        };

        xhr.get('/system/reload-httpd/', {
            sync: true
        }).then(handle, handle);

    }

    ask_service = function(srv) {

        dialog = new Dialog({
            title: 'Enable service',
            href: '/services/enable/'+srv+'/',
            parseOnLoad: true,
            closable: true,
            style: "max-width: 75%;max-height:70%;background-color:white;overflow:auto;",
            onHide: function() {
                setTimeout(lang.hitch(this, 'destroyRecursive'), manager.defaultDuration);
            },
        });
        dialog.show();

    }

    add_formset = function(a, url, name) {

        xhr.get(url, {
            query: {
                fsname: name,
            },
            sync: true
            }).then(function(data) {

                var extra = registry.byId("id_"+name+"-TOTAL_FORMS");
                var extran = extra.get("value");
                data = data.replace(/__prefix__/g, extran);
                var div = domConstruct.create("table");
                query(a.parentNode.parentNode).before(div);
                div.innerHTML = data;
                parser.parse(div);
                extra.set('value', parseInt(extran) + 1);

            });

    }

    formsetAddForm = function(attrs) {

        xhr.get(attrs['url'], {
            query: {
                prefix: attrs['prefix'],
            },
            sync: true
            }).then(function(data) {

                var extra = registry.byId("id_"+attrs['prefix']+"-TOTAL_FORMS");
                var extran = extra.get("value");
                var data = data.replace(new RegExp(attrs['emptyholder'], 'g'), extran);
                var tr = domConstruct.create("tr");

                tr.innerHTML = data;
                parser.parse(tr);

                if(typeof(attrs.insertItems) != 'undefined') {
                    attrs['insertItems'](tr.childNodes);
                } else if(typeof(attrs.insert) != 'undefined') {
                    attrs['insert'](tr);
                }
                extra.set('value', parseInt(extran) + 1);

            });

    }


    toggle_service = function(obj, onSuccess) {
        var td = obj.parentNode;
        var n = domConstruct.create("div", {  }, td);
        domClass.add(n, "dijitIconLoading");
        domStyle.set(n, "height", "25px");
        domStyle.set(n, "float", "left");

        xhr.post("/services/toggle/"+obj.name+"/", {
            data: "Some random text",
            handleAs: "json"
            }).then(function(data) {
                if(data.status == 'on') {
                    obj.src = '/static/images/ui/buttons/on.png';
                } else if(data.status == 'off') {
                    obj.src = '/static/images/ui/buttons/off.png';
                }
                if(data.error) {
                    setMessage(data.message, "error");
                }
                domConstruct.destroy(n);
                if(onSuccess) onSuccess();
            },
            function(error) {
                //alert
            });

    }


    togglePluginService = function(from, name) {

        var td = from.parentNode;
        var _status = domAttr.get(from, "status");
        var action;
        var n = domConstruct.create("div", {}, td);
        domClass.add(n, "dijitIconLoading");
        domStyle.set(n, "height", "25px");
        domStyle.set(n, "float", "left");

        if(_status == "on") {
            action = "stop";
        } else {
            action = "start";
        }

        var checkStatus = function(name) {

            xhr.get("/plugins/"+name+"/_s/status", {
                handleAs: "json"
                }).then(function(data) {
                    if(data.status == 'RUNNING') {
                        from.src = '/static/images/ui/buttons/on.png';
                        domAttr.set(from, "status", "on");
                    } else if(data.status == 'STOPPED') {
                        from.src = '/static/images/ui/buttons/off.png';
                        domAttr.set(from, "status", "off");
                    } else {
                        setTimeout('checkStatus(name);', 1000);
                        return;
                    }
                    if(data.error) {
                        setMessage(data.message, "error");
                    }
                    domConstruct.destroy(n);
                },
                function(evt) {
                    setMessage(gettext("Some error occurred"), "error");
                    domConstruct.destroy(n);
                });

        }

        var deferred = xhr.get("/plugins/" + name + "/_s/" + action, {
            handleAs: "text"
            }).then(function(data) {
                try {
                    var json = JSON.parse(data);
                    if(json && json.error == true) {
                        setMessage(json.message, 'error');
                    }
                } catch(e) {}
                setTimeout(function() { checkStatus(name); }, 1000);
            },
            function(evt) {
                domConstruct.destroy(n);
                setMessage(gettext("Some error occurred"), "error");
            });
        return deferred;

    }

    buttongrid = function(v) {
        var json = JSON.parse(v);
        parser.parse(dom.byId(this.id));
        var gridhtml = registry.getEnclosingWidget(dom.byId(this.id));

        var content = new ContentPane({});
        var b = new Button({
            label: gettext("Edit")
        });

        on(b, 'click', function(){
            editObject(gettext('Edit Disk'), json.edit_url, [gridhtml,]);
        });
        content.domNode.appendChild(b.domNode);

        var b = new Button({
            label: gettext("Wipe")
        });

        on(b, 'click', function(){
            editObject(gettext('Wipe Disk'), json.wipe_url, [gridhtml,]);
        });
        content.domNode.appendChild(b.domNode);

        return content;
    }

    var canceled = false;

    toggleGeneric = function(checkboxid, farray, inverted) {

        if(inverted == undefined) inverted = false;

        var box = registry.byId(checkboxid);
        if(inverted == true) {
            toset = !box.get("value");
        } else{
            toset = box.get("value");
        }
        for(var i=0;i<farray.length;i++) {
            registry.byId(farray[i]).set('disabled', toset);
        }

    }

    rsyncModeToggle = function() {

        var select = registry.byId("id_rsync_mode");
        var modname = registry.byId("id_rsync_remotemodule");
        var path = registry.byId("id_rsync_remotepath");
        var port = registry.byId("id_rsync_remoteport");
        var trm = modname.domNode.parentNode.parentNode;
        var trp = path.domNode.parentNode.parentNode;
        var trpo = port.domNode.parentNode.parentNode;
        if(select.get('value') == 'ssh') {
            domStyle.set(trm, "display", "none");
            domStyle.set(trp, "display", "table-row");
            domStyle.set(trpo, "display", "table-row");
        } else {
            domStyle.set(trm, "display", "table-row");
            domStyle.set(trp, "display", "none");
            domStyle.set(trpo, "display", "none");
        }

    }

    setMessage = function(msg, css) {

        if(!css) css = "success";
        var footer = dom.byId("messages");
        domConstruct.empty(footer);
        var suc = domConstruct.create("div");
        on(suc, 'click', function() {
            dFx.fadeOut({ node: suc }).play();
        });
        footer.appendChild(suc);
        domClass.add(suc, css);
        html.set(suc, "<p>"+msg+"</p>");
        setTimeout(function() { if(suc) dFx.fadeOut({node: suc}).play();}, 7000);

    };

    serviceFailed = function(srv) {
        var obj = query("img#"+srv+"_toggle");
        if(obj.length > 0) {
            obj = obj[0];
            toggle_service(obj);
        }
    }

    handleJson = function(rnode, data) {

        if(data.type == 'page') {
            rnode.set('content', data.content);
        } else if(data.type == 'form') {

            form = registry.byId(data.formid);
            query(".errorlist", form.domNode).forEach(function(item, idx) {
                domConstruct.destroy(item);
            });
            if(data.error == true) {
                var first = null;
                for(key in data.errors) {

                    field = query("input[name="+key+"],textarea[name="+key+"],select[name="+key+"]", form.domNode);
                    if(field.length == 0) {
                        console.log("Form element not found: ", key);
                        continue;
                    }
                    field = registry.getEnclosingWidget(field[0]);
                    if(!first && field.focus)
                        first = field;
                    var ul = domConstruct.create('ul', {style: {display: "none"}}, field.domNode.parentNode, "first");
                    domAttr.set(ul, "class", "errorlist");
                    for(var i=0; i<data.errors[key].length;i++) {
                        var li = domConstruct.create('li', {innerHTML: data.errors[key][i]}, ul);
                    }
                    fx.wipeIn({
                        node: ul,
                        duration: 300
                    }).play();

                }

                if(first) first.focus();

            } else {
                //form.reset();
                if(rnode.isInstanceOf(dijit.Dialog))
                    rnode.hide();
            }

        } else {

            if(rnode.isInstanceOf(dijit.Dialog) && (data.error == false || (data.error == true && !data.type) ) ) {
                rnode.hide();
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


    }

    checkProgressBar = function(pbar, url, uuid, iter) {
        var progress_url;
        if(typeof(url) == 'string') {
             progress_url = url;
        } else {
             progress_url = '/progress';
        }
        if(!iter) iter = 0;
        xhr.get(progress_url, {
            headers: {"X-Progress-ID": uuid}
            }).then(function(data) {
                var obj = eval(data);
                if(obj.state == 'uploading') {
                    var perc = Math.ceil((obj.received / obj.size)*100);
                    if(perc == 100) {
                        pbar.update({'indeterminate': true});
                        return;
                    } else {
                        pbar.update({maximum: 100, progress: perc, indeterminate: false});
                    }
                }
                if(obj.state == 'starting' || obj.state == 'uploading') {
                    if(obj.state == 'starting' && iter >= 3) {
                        return;
                    }
                    setTimeout(function() {
                         checkProgressBar(pbar, url, uuid, iter + 1);
                         }, 1000);
                }
            });
    }

    doSubmit = function(attrs) {

        var pbar, uuid, multipart, rnode, newData;

        if(!attrs) {
            attrs = {};
        }

        query('input[type=button],input[type=submit]', attrs.form.domNode).forEach(
            function(inputElem){
                if(inputElem.type == 'submit') {
                    var dj = registry.getEnclosingWidget(inputElem);
                    if(dj) {
                        if(dj.isInstanceOf(dojox.form.BusyButton)) {
                            dj.busyLabel = 'Please wait...';
                        } else {
                            domAttr.set(dj.domNode, "oldlabel", dj.get('label'));
                            dj.set('label', gettext('Please wait...'));
                        }
                    }
                }
                registry.getEnclosingWidget(inputElem).set('disabled',true);
            }
            );

        // prevent the default submit
        dEvent.stop(attrs.event);
        newData = attrs.form.get("value");
        newData['__form_id'] = attrs.form.id;

        multipart = query("input[type=file]", attrs.form.domNode).length > 0;

        rnode = getDialog(attrs.form);
        if(!rnode) rnode = registry.getEnclosingWidget(attrs.form.domNode.parentNode);

        loadOk = function(data, req) {

            query('input[type=button],input[type=submit]', attrs.form.domNode).forEach(
                  function(inputElem){
                       registry.getEnclosingWidget(inputElem).set('disabled',false);
                   }
                );
            var sbtn = registry.getEnclosingWidget(query('input[type=submit]', attrs.form.domNode)[0]);
            if(sbtn) {
                if(domAttr.has(sbtn.domNode, "oldlabel")) {
                    sbtn.set('label', domAttr.get(sbtn.domNode, "oldlabel"));
                } else {
                    sbtn.set('label', 'Save');
                }
                if(sbtn.isInstanceOf(dojox.form.BusyButton)) sbtn.resetTimeout();
            }
            handleJson(rnode, data);

            if('onComplete' in attrs) {
                attrs.onComplete(data);
            }

        };

        var handleReq = function(data, ioArgs, error) {
            var json;
            if(pbar) {
                pbar.destroy();
                domStyle.set(attrs.form.domNode, "display", "block");
                //rnode.layout();
                rnode._size();
                rnode._position();
            }
            try {
                json = JSON.parse(data);
                if(json.error != true && json.error != false) throw "toJson error";
                loadOk(json, ioArgs);
            } catch(e) {
                console.log(e);
                setMessage(gettext('An error occurred!'), "error");
                try {
                    if(!error) {
                        rnode.set('content', data);
                    } else {
                        rnode.hide();
                    }
                } catch(e) {}
            }
        };

        if (attrs.progressbar != undefined) {
            pbar = dijit.ProgressBar({
                style: "width:300px",
                indeterminate: true,
                });
            /*
             * We cannot destroy form node, that's why we just hide it
             * otherwise iframe.send won't work, it expects the form domNode
             */
            attrs.form.domNode.parentNode.appendChild(pbar.domNode);
            domStyle.set(attrs.form.domNode, "display", "none");
            //rnode.layout();
            rnode._size();
            rnode._position();

        }

        if( multipart ) {

            uuid = generateRandomUuid();
            iframe.post(attrs.url + '?X-Progress-ID=' + uuid, {
                //form: item.domNode,
                data: {__form_id: attrs.form.id},
                form: attrs.form.id,
                handleAs: 'text'
                }).then(handleReq, function(evt) {
                    handleReq(evt.response.data, evt.response, true);
                });

        } else {

            xhr.post(attrs.url, {
                data: newData,
                handleAs: 'text'
            }).then(handleReq, function(evt) {
                handleReq(evt.response.data, evt.response, true);
                });

        }

        if (attrs.progressbar != undefined) {
            checkProgressBar(pbar, attrs.progressbar, uuid);
        }

    }


    formSubmit = function(item, e, url, callback, attrs) {
        dEvent.stop(e); // prevent the default submit
        if(!attrs) {
            attrs = {};
        }
        var qry = query('.saved', item.domNode)[0];
        if(qry) domStyle.set(qry, 'display', 'none');

        query('input[type=button],input[type=submit]', item.domNode).forEach(
          function(inputElem){
               if(inputElem.type == 'submit') {
                   var dj = registry.getEnclosingWidget(inputElem);
                   if(dj) {
                       if(dj.isInstanceOf(dojox.form.BusyButton)) {
                           dj.busyLabel = 'Please wait...';
                       } else {
                           domAttr.set(dj.domNode, "oldlabel", dj.get('label'));
                           dj.set('label', gettext('Please wait...'));
                       }
                   }
               }
               registry.getEnclosingWidget(inputElem).set('disabled',true);
           }
        );

        var rnode = getDialog(item);
        if(!rnode) rnode = registry.getEnclosingWidget(item.domNode.parentNode);
        if(!rnode) rnode = registry.byId("edit_dialog");

        var loadOk = function(data) {

            try {
                var json = JSON.parse(data);
                // TODO, workaound for firefox, it does parse html as JSON!!!
                if(json.error != true && json.error != false) {
                    throw "not json"
                }

                try {
                    rnode.hide();
                } catch(err2) {
                    query('input[type=button],input[type=submit]', item.domNode).forEach(
                      function(inputElem){
                           registry.getEnclosingWidget(inputElem).set('disabled',false);
                       }
                    );
                    var sbtn = registry.getEnclosingWidget(query('input[type=submit]', item.domNode)[0]);
                    if(domAttr.has(sbtn.domNode, "oldlabel")) {
                        sbtn.set('label', domAttr.get(sbtn.domNode, "oldlabel"));
                    } else {
                        sbtn.set('label', 'Save');
                    }
                    if(sbtn.isInstanceOf(BusyButton)) sbtn.resetTimeout();
                }
                if(json.error == false){
                    query('ul[class=errorlist]', rnode.domNode).forEach(function(i) { i.parentNode.removeChild(i); });
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
                    var qry = query('#success', rnode.domNode);
                    if(qry.length>0)
                        dFx.fadeOut({node: rnode, onEnd: function() { rnode.hide(); }}).play();
                } catch(err) {}
            }
        };

        var errorHandle = function(evt) {
            var data = evt.response.data;

            setMessage(gettext('An error occurred!'), "error");

            try {
               rnode.hide();
            } catch(err2) {
                query('input[type=button],input[type=submit]', item.domNode).forEach(
                  function(inputElem){
                       registry.getEnclosingWidget(inputElem).set('disabled',false);
                   }
                );

                registry.getEnclosingWidget(query('input[type=submit]', item.domNode)[0]).set('label','Save');
            }
        }

        // are there any files to be submited?
        var files = query("input[type=file]", item.domNode);
        if(files.length > 0) {

            var uuid, pbar;
            if (attrs.progressbar == true) {
                pbar = dijit.ProgressBar({
                    style: "width:300px",
                    indeterminate: true,
                    });
                /*
                 * We cannot destroy form node, that's why we just hide it
                 * otherwise iframe.send won't work, it expects the form domNode
                 */
                item.domNode.parentNode.appendChild(pbar.domNode);
                domStyle.set(item.domNode, "display", "none")
                //rnode.layout();
                rnode._size();
                rnode._position();

            }
            uuid = generateRandomUuid();
            iframe.post(url + '?iframe=true&X-Progress-ID=' + uuid, {
                form: item.domNode,
                handleAs: 'text',
                }).then(loadOk, errorHandle);
            checkProgressBar(pbar, true, uuid);

        } else {

            var newData = item.get("value");
            if (attrs.progressbar == true) {
                rnode.set('content', '<div style="width:300px" data-dojo-props="indeterminate: true" data-dojo-type="dijit.ProgressBar"></div>');
            }
            xhr.post(url, {
                data: newData,
                handleAs: 'text'
             }).then(loadOk, errorHandle);

         }

    }

    checkNumLog = function(unselected) {
        var num = 0;
        for(var i=0;i<unselected.length;i++) {
            var q = query("input[name=zpool_"+unselected[i]+"]:checked");
            if(q.length > 0) {
                if(q[0].value == 'log')
                num += 1;
            }
        }

        var lowlog = dom.byId("lowlog");
        if(!lowlog) return;

        if(num == 1) {
            domStyle.set(lowlog, "display", "");
        } else {
            domStyle.set(lowlog, "display", "none");
        }
    }

    taskrepeat_checkings = function() {

        var repeat = registry.byId("id_task_repeat_unit");
        wk = query(registry.byId('id_task_byweekday_0').domNode).parents("tr").first()[0];
        if(repeat.get('value') != 'weekly') {
            domStyle.set(wk, "display", "none");
        } else {
            domStyle.set(wk, "display", "");
        }

    }

    wizardcheckings = function(vol_change, first_load) {

        if(!registry.byId("wizarddisks")) return;
        var add = registry.byId("id_volume_add");
        var add_mode = false;
        if(add && add.get("value") != '') {
            add_mode = true;
        }
        var disks = registry.byId("wizarddisks");
        var d = disks.get('value');
        html.set(dom.byId("wizard_num_disks"), d.length + '');

        var zfs = query("input[name=volume_fstype]")[1].checked || add_mode;

        registry.byId("id_volume_name").set('disabled', add_mode);
        query("input[name=volume_fstype]").forEach(function(item, idx) {
            var wg = registry.getEnclosingWidget(item);
            if(wg && add_mode && domAttr.get(item, 'value') == 'ZFS') {
                wg.set('checked', true);
            }
        });

        if(vol_change == true) {
            var unselected = [];
            disks.invertSelection(null);
            var opts = disks.get("value");
            for(var i=0;i<opts.length;i++) {
                unselected.push(opts[i]);
            }
            disks.invertSelection(null);

            if(unselected.length > 0 && zfs == true && first_load != true) {

                var tab = dom.byId("disks_unselected");
                query("#disks_unselected tbody tr").orphan();
                var txt = "";
                var toappend = [];
                for(var i=0;i<unselected.length;i++) {
                    var tr = domConstruct.create("tr");
                    var td = domConstruct.create("td", {innerHTML: unselected[i]});
                    tr.appendChild(td);

                    var td = domConstruct.create("td");
                    var rad = new RadioButton({ checked: true, value: "none", name: "zpool_"+unselected[i]});
                    on(rad, 'click', function() {checkNumLog(unselected);});
                    td.appendChild(rad.domNode);
                    tr.appendChild(td);

                    var td = domConstruct.create("td");
                    var rad = new RadioButton({ value: "log", name: "zpool_"+unselected[i]});
                    on(rad, 'click', function() {checkNumLog(unselected);});
                    td.appendChild(rad.domNode);
                    tr.appendChild(td);

                    var td = domConstruct.create("td");
                    var rad = new RadioButton({ value: "cache", name: "zpool_"+unselected[i]});
                    on(rad, 'click', function() {checkNumLog(unselected);});
                    td.appendChild(rad.domNode);
                    tr.appendChild(td);

                    var td = domConstruct.create("td");
                    var rad = new RadioButton({ value: "spare", name: "zpool_"+unselected[i]});
                    on(rad, 'click', function() {checkNumLog(unselected);});
                    td.appendChild(rad.domNode);
                    tr.appendChild(td);

                    toappend.push(tr);
                }

                for(var i=0;i<toappend.length;i++) {
                    domConstruct.place(toappend[i], query("#disks_unselected tbody")[0]);
                }

               domStyle.set("zfsextra", "display", "");

            } else {
                if(zfs == true && first_load == true) {
                    domStyle.set("zfsextra", "display", "");
                } else {
                    query("#disks_unselected tbody tr").orphan();
                    domStyle.set("zfsextra", "display", "none");
                }
            }
        } else if(zfs == false) {
               domStyle.set("zfsextra", "display", "none");
        }

        var ufs = query("#fsopt input")[0].checked;
        var zfs = query("#fsopt input")[1].checked;
        if(d.length >= 2) {
            domStyle.set("grpopt", "display", "");
        } else {
            domStyle.set("grpopt", "display", "none");
            query("input[name=group_type]:checked").forEach(function(tag) {
                var dtag = registry.getEnclosingWidget(tag);
                if(dtag) dtag.set('checked', false);
            });
        }

        if(zfs) {
            domStyle.set('zfssectorsize', 'display', 'table-row');
            domStyle.set('zfsfulldiskencryption', 'display', 'table-row');
            domStyle.set('zfsdedup', 'display', 'table-row');
        } else {
            domStyle.set('zfssectorsize', 'display', 'none');
            domStyle.set('zfsfulldiskencryption', 'display', 'none');
            domStyle.set('zfsdedup', 'display', 'none');
        }

        if(ufs) {
            domStyle.set("ufspath", "display", "table-row");
            domStyle.set("ufspathen", "display", "table-row");
        } else {
            domStyle.set("ufspath", "display", "none");
            domStyle.set("ufspathen", "display", "none");
        }

        if(d.length >= 3 && zfs) {
            domStyle.set("grpraidz", "display", "block");
        } else {
            domStyle.set("grpraidz", "display", "none");
        }

        if(d.length >= 4 && zfs) {
            domStyle.set("grpraidz2", "display", "block");
        } else {
            domStyle.set("grpraidz2", "display", "none");
        }

        if(d.length >= 5 && zfs) {
            domStyle.set("grpraidz3", "display", "block");
        } else {
            domStyle.set("grpraidz3", "display", "none");
        }

        if(ufs && d.length-1 >= 2 && (((d.length-2)&(d.length-1)) == 0)) {
            if(ufs)
                domStyle.set("grpraid3", "display", "block");
        } else {
            domStyle.set("grpraid3", "display", "none");
        }
    }

    getDialog = function(from) {

        var turn = from;
        while(1) {
            turn = registry.getEnclosingWidget(turn.domNode.parentNode);
            if(turn == null) return null;
            if(turn.isInstanceOf(dijit.Dialog)) break;
        }
        return turn;

    };

    getForm = function(from) {

        var turn = from;
        while(1) {
            turn = registry.getEnclosingWidget(turn.domNode.parentNode);
            if(turn.isInstanceOf(dijit.form.Form)) break;
        }
        return turn;

    };

    cancelDialog = function(from) {

        var dialog = getDialog(from);
        canceled = true;
        dialog.hide();

    };

    refreshTree = function() {
        var fadeArgs = {
           node: "fntree",
           onEnd: function() { registry.byId("fntree").reload(); }
         };
        dFx.fadeOut(fadeArgs).play();
    }

    refreshTabs = function(nodes) {
        if(nodes && canceled == false) {
            refreshTree();
            dArray.forEach(nodes, function(entry, i) {
                if(entry.isInstanceOf && entry.isInstanceOf(dijit.layout.ContentPane)) {
                    entry.refresh();
                    var par = registry.getEnclosingWidget(entry.domNode.parentNode);
                    par.selectChild(entry);
                    var par2 = registry.getEnclosingWidget(par.domNode.parentNode);
                    if(par2 && par2.isInstanceOf(dijit.layout.ContentPane))
                        registry.byId("content").selectChild(par2);
                } else {
                    if(entry.domNode) entry = entry.domNode;
                    var par = query(entry).parents(".objrefresh").first()[0];
                    var cp = registry.getEnclosingWidget(par);
                    if(cp) cp.refresh();
                }
            });

        }
    }

    refreshPlugins = function() {
        var par = query("#plugins_settings").parents(".objrefresh").first()[0];
        var cp = registry.getEnclosingWidget(par);
        if(cp) cp.refresh();
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
        dialog = new Dialog({
            id: attrs.id,
            title: attrs.name,
            href: attrs.url,
            parseOnLoad: true,
            closable: true,
            style: attrs.style,
            onHide: function() {
                setTimeout(lang.hitch(this, function() {
                    this.destroyRecursive();
                }), manager.defaultDuration);
                refreshTabs(attrs.nodes);
            },
            onLoad: function() {
                processStack();
                //this.layout(); // dojo 1.7
                this._position(); // dojo 1.8
            }
        });
        if(attrs.onLoad) {
            f = lang.hitch(dialog, attrs.onLoad);
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
            url: url,
            nodes: nodes
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

    viewModel = function(name, url, tab) {
        var p = registry.byId("content");
        var c = p.getChildren();
        for(var i=0; i<c.length; i++){
            if(c[i].title == name){
                c[i].href = url;
                p.selectChild(c[i]);
                return;
            }
        }
        var pane = new ContentPane({
            href: url,
            title: name,
            closable: true,
            parseOnLoad: true,
            refreshOnShow: true,
        });
        if(tab)
            pane.tab = tab;
        domClass.add(pane.domNode, "objrefresh" );
        p.addChild(pane);
        p.selectChild(pane);
    }


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
          xhrArgs.headers["X-CSRFToken"] = cookie('csrftoken');
          return originalXHR(httpVerb, xhrArgs, hasHTTPBody);
        }

        ready(function() {

            menuSetURLs();
            Menu.openSystem();
            var store = new JsonRestStore({
                target: "/admin/menu.json",
                labelAttribute: "name",
            });

            var treeModel = new ForestStoreModel({
                store: store,
                query: {},
                rootId: "root",
                rootLabel: "FreeNAS",
                childrenAttrs: ["children"]
            });

            var treeclick = function(item) {
                var p = registry.byId("content");

                if(item.type == 'object' ||
                   item.type == 'dialog' ||
                   item.type == 'scary_dialog' ||
                   item.type == 'editobject' ||
                   item.type == 'volumewizard'
                    ) {
                    var data = query(".data_"+item.app_name+"_"+item.model);
                    var func;

                    if(item.type == 'volumewizard') func = volumeWizard;
                    else if(item.type == 'scary_dialog') func = editScaryObject;
                    else func = editObject;

                    if(data) {
                        widgets = [];
                        data.forEach(function(item, idx) {
                            widget = registry.getEnclosingWidget(item);
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
                } else if(item.type == 'pluginsfcgi') {
                    Menu.openPluginsFcgi(p, item);
                } else if(item.type == 'openaccount') {
                    Menu.openAccount(item.gname);
                } else if(item.type == 'iscsi') {
                    Menu.openISCSI(item.gname);
                } else if(item.type == 'logout') {
                    dWindow.location='/account/logout/';
                } else if(item.action == 'displayprocs') {
                    registry.byId("top_dialog").show();
                } else if(item.action == 'shell') {
                    registry.byId("shell_dialog").show();
                } else if(item.type == 'opensharing') {
                    Menu.openSharing(item.gname);
                } else if(item.type == 'openstorage') {
                    Menu.openStorage(item.gname);
                } else if(item.type == 'viewmodel') {
                    //  get the children and make sure we haven't opened this yet.
                    var c = p.getChildren();
                    for(var i=0; i<c.length; i++){
                        if(c[i].title == item.name){
                            p.selectChild(c[i]);
                            return;
                        }
                    }
                    var pane = new ContentPane({
                        id: "data_"+item.app_name+"_"+item.model,
                        href: item.url,
                        title: item.name,
                        closable: true,
                        refreshOnShow: true,
                        parseOnLoad: true,
                    });
                    p.addChild(pane);
                    domClass.add(pane.domNode, ["objrefresh","data_"+item.app_name+"_"+item.model] );
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
                    var pane = new ContentPane({
                        href: item.url,
                        title: item.name,
                        closable: true,
                        parseOnLoad: true,
                    });
                    pane.tab = item.gname;
                    domClass.add(pane.domNode, ["objrefresh","data_"+item.app_name+"_"+item.model] );
                    p.addChild(pane);
                    p.selectChild(pane);
                }

            };

                mytree = new Tree({
                    id: "fntree",
                    model: treeModel,
                    showRoot: false,
                    onClick: treeclick,
                    onLoad: function() {
                        var fadeArgs = {
                           node: "fntree",
                         };
                        dFx.fadeIn(fadeArgs).play();
                    },
                    openOnClick: true,
                    getIconClass: function(item, opened) {
                        if(item.icon && item.icon.search("/") == -1)
                            return item.icon;
                    },
                    getIconStyle: function(item, opened) {
                        if(item.icon && item.icon.search("/") != -1)
                            return {
                                backgroundImage: "url("+item.icon+")",
                                height: '16px',
                                width: '16px'
                                };
                    },
                }
                );
                registry.byId("menupane").set('content', mytree);

                var shell = new ESCDialog({
                    id: "shell_dialog",
                    content: '<pre class="ix" tabindex="1" id="shell_output">Loading...</pre>',
                    style: "min-height:400px;background-color: black;",
                    title: 'Shell',
                    region: 'center',
                    connections: [],
                    onShow: function() {

                        function handler(msg,value) {
                            switch(msg) {
                            case 'conn':
                                //startMsgAnim('Tap for keyboard',800,false);
                                break;
                            case 'disc':
                                //startMsgAnim('Disconnected',0,true);
                                delete _webshell;
                                _webshell = undefined;
                                registry.byId("shell_dialog").hide();
                                break;
                            case 'curs':
                                cy=value;
                                //scroll(cy);
                                break;
                            }
                        }

                        try {
                            _webshell.start();
                        } catch(e) {
                            _webshell=new WebShell({
                                node: "shell_output",
                                handler: handler
                                });
                            _webshell.start();
                        }

                    },
                    onHide: function(e) {
                        if(_webshell)
                            _webshell.stop();
                    }
                }, "shell_dialog_holder");

        });
    });
