#+
# Copyright 2010 iXsystems
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# $FreeBSD$
#####################################################################

from freenasUI.account.forms import * 
from freenasUI.account.models import * 
from django.forms.models import modelformset_factory
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import password_change_done
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.contrib.auth import authenticate, login, logout
from django.template import RequestContext
from django.http import Http404, HttpResponse
from django.views.generic.list_detail import object_detail, object_list
from django.views.generic.create_update import update_object, delete_object
from django.utils import simplejson
from freenasUI.middleware.notifier import notifier
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, PasswordChangeForm
from forms import SetPasswordForm, PasswordChangeForm
from django.views.decorators.csrf import csrf_protect
import os, commands
from django.core.urlresolvers import reverse

@csrf_protect
@login_required
def bsdUsersView(request, objtype = None, post_change_redirect=None, password_change_form=PasswordChangeForm):
    if objtype != None and objtype != 'bsdgroup':
        focus_form = objtype
    else:
        focus_form = 'bsduser'

    bsduser = bsdUserCreationForm()
    passform = password_change_form(user=request.user, data=request.GET)
    changeform = UserChangeForm(instance=request.user)
    bsdgroup = bsdGroupsForm()
    bsduser_list = bsdUsers.objects.order_by("id").select_related().filter(bsdusr_builtin=False)
    bsduser_list_builtin = bsdUsers.objects.order_by("id").select_related().filter(bsdusr_builtin=True)
    bsdgroup_list = bsdGroups.objects.order_by("id").filter(bsdgrp_builtin=False)
    bsdgroup_list_builtin = bsdGroups.objects.order_by("id").filter(bsdgrp_builtin=True)

    #if post_change_redirect is None:
     #   post_change_redirect = reverse('django.contrib.auth.views.password_change_done')
    if request.method == 'POST':
        if objtype == 'passform':
            passform = password_change_form(user=request.user, data=request.POST)
            if passform.is_valid():
                passform.save()
        elif objtype == 'changeform':
            changeform = UserChangeForm(instance=request.user, data=request.POST)
            if changeform.is_valid():
                changeform.save()
        elif objtype == 'bsduser':
            bsduser = bsdUserCreationForm(request.POST)
            if bsduser.is_valid():
                bsduser.save()
        elif objtype == 'bsdgroup':
            bsdgroup = bsdGroupsForm(request.POST)
            if bsdgroup.is_valid():
                bsdgroup.save()
        else: 
            raise Http404()
    variables = RequestContext(request, {
        'focused_tab' : 'account',
        'passform': passform,
        'changeform': changeform,
        'bsduser': bsduser,
        'bsdgroup': bsdgroup,
        'bsduser_list': bsduser_list,
        'bsduser_list_builtin': bsduser_list_builtin,
        'bsdgroup_list': bsdgroup_list,
        'bsdgroup_list_builtin': bsdgroup_list_builtin,
        'focus_form': focus_form,
    })
    return render_to_response('account/index.html', variables)

@login_required
def home(request):
    focus_form = request.GET.get('tab', 'passform')
    password_change_form=PasswordChangeForm

    bsduser = bsdUserCreationForm()
    passform = password_change_form(user=request.user, data=request.GET)
    changeform = UserChangeForm(instance=request.user)
    bsdgroup = bsdGroupsForm()

    #if post_change_redirect is None:
    #   post_change_redirect = reverse('django.contrib.auth.views.password_change_done')
    if request.method == 'POST':
        if objtype == 'passform':
            passform = password_change_form(user=request.user, data=request.POST)
            if passform.is_valid():
                passform.save()
        elif objtype == 'changeform':
            changeform = UserChangeForm(instance=request.user, data=request.POST)
            if changeform.is_valid():
                changeform.save()
        elif objtype == 'bsduser':
            bsduser = bsdUserCreationForm(request.POST)
            if bsduser.is_valid():
                bsduser.save()
        elif objtype == 'bsdgroup':
            bsdgroup = bsdGroupsForm(request.POST)
            if bsdgroup.is_valid():
                bsdgroup.save()
        else: 
            raise Http404()
    variables = RequestContext(request, {
        'focused_tab' : 'account',
        'passform': passform,
        'changeform': changeform,
        'bsduser': bsduser,
        'bsdgroup': bsdgroup,
        'focus_form': focus_form,
    })
    return render_to_response('account/index2.html', variables)

@login_required
def bsduser(request):

    bsduser_list = bsdUsers.objects.order_by("id").select_related().filter(bsdusr_builtin=False)
    bsduser_list_builtin = bsdUsers.objects.order_by("id").select_related().filter(bsdusr_builtin=True)

    variables = RequestContext(request, {
        'bsduser_list': bsduser_list,
        'bsduser_list_builtin': bsduser_list_builtin,
    })
    return render_to_response('account/bsdusers.html', variables)

@login_required
def bsdgroup(request):

    bsdgroup_list = bsdGroups.objects.order_by("id").filter(bsdgrp_builtin=False)
    bsdgroup_list_builtin = bsdGroups.objects.order_by("id").filter(bsdgrp_builtin=True)

    variables = RequestContext(request, {
        'bsdgroup_list': bsdgroup_list,
        'bsdgroup_list_builtin': bsdgroup_list_builtin,
    })
    return render_to_response('account/bsdgroups.html', variables)

@login_required
def usergroup_delete(request, object_id, objtype):
    account_model_map = {
        'bsduser':   bsdUsers,
        'bsdgroup':   bsdGroups,
    }
    obj = account_model_map[objtype].objects.get(id=object_id)
    if objtype == 'bsduser':
        if obj.bsdusr_builtin == True:
            raise ValueError(_("User %s is built-in and can not be deleted!") % (obj.bsdusr_username))
    else:
        if obj.bsdgrp_builtin == True:
            raise ValueError(_("Group %s is built-in and can not be deleted!") % (obj.bsdgrp_group))
    if request.method == 'POST':
        if objtype == 'bsduser':
            notifier().user_deleteuser(obj.bsdusr_username.__str__())
            try:
                gobj = bsdGroups.objects.get(bsdgrp_group = obj.bsdusr_username)
                if not gobj.bsdgrp_builtin:
                    gobj.delete()
            except:
                pass
        else:
            notifier().user_deletegroup(obj.bsdgrp_group.__str__())
        obj.delete()
        notifier().reload("user")
        return HttpResponseRedirect('/account/')
    else:
        c = RequestContext(request, {
            'focused_tab' : 'account',
            'object': obj,
        })
        return render_to_response(('account/%ss_confirm_delete.html' % objtype), c)

@login_required
def generic_update(request, object_id, objtype):
    objtype2form = {
            'bsduser':   ( bsdUsers, bsdUserChangeForm ),
            'bsdgroup':   ( bsdGroups, bsdGroupsForm ),
            } 
    model, form_class = objtype2form[objtype]
    return update_object(
        request = request,
        model = model, form_class = form_class,
        object_id = object_id, 
        post_save_redirect = '/account/',
        )

@login_required
def password_change2(request):

    extra_context = {}
    password_change_form=PasswordChangeForm
    passform = password_change_form(user=request.user)
    changeform = UserChangeForm(instance=request.user)

    if request.method == 'POST':
        passform = password_change_form(user=request.user, data=request.POST)
        if passform.is_valid():
            passform.save()
            extra_context.update({ 'saved' : True, })
            passform = password_change_form(user=request.user)


    extra_context.update({ 'passform' : passform, })
    variables = RequestContext(request, extra_context)
    return render_to_response('account/passform.html', variables)

@login_required
def user_change(request):

    extra_context = {}
    changeform = UserChangeForm(instance=request.user)

    if request.method == 'POST':
        changeform = UserChangeForm(instance=request.user, data=request.POST)
        if changeform.is_valid():
            changeform.save()
            extra_context.update({ 'saved' : True, })


    extra_context.update({ 'changeform' : changeform, })
    variables = RequestContext(request, extra_context)
    return render_to_response('account/changeform.html', variables)

@login_required
def password_update(request, object_id):
    obj = bsdUsers.objects.get(id=object_id)
    if request.method == 'POST':
        f = bsdUserPasswordForm(request.POST, instance=obj)
        if f.is_valid():
            f.save()
            return HttpResponseRedirect('/account/')
    else:
        f = bsdUserPasswordForm(instance=obj)
    variables = RequestContext(request, {
        'focused_tab' : 'account',
        'form' : f,
        'object' : obj,
    })
    return render_to_response('account/bsdaccount_form.html', variables)

@login_required
def group2user_update(request, object_id):
    if request.method == 'POST':
        f = bsdGroupToUserForm(object_id, request.POST)
        if f.is_valid():
            f.save()
            return HttpResponseRedirect('/account/')
    else:
        f = bsdGroupToUserForm(groupid=object_id)
    variables = RequestContext(request, {
        'focused_tab' : 'account',
        'form' : f,
    })
    return render_to_response('account/bsdgroup2user_form.html', variables)

@login_required
def group2user_update2(request, object_id):
    if request.method == 'POST':
        f = bsdGroupToUserForm(object_id, request.POST)
        if f.is_valid():
            f.save()
            return HttpResponse(simplejson.dumps({"error": False, "message": _("%s successfully update.") % _("Users")}), mimetype="application/json")
            #return render_to_response('account/bsdgroup2user_form_ok.html')
    else:
        f = bsdGroupToUserForm(groupid=object_id)
    variables = RequestContext(request, {
        'url': reverse('account_bsdgroup_members', kwargs={'object_id':object_id}),
        'form' : f,
    })
    return render_to_response('account/bsdgroup2user_form2.html', variables)

@login_required
def user2group_update(request, object_id):
    if request.method == 'POST':
        f = bsdUserToGroupForm(object_id, request.POST)
        if f.is_valid():
            f.save()
            return HttpResponseRedirect('/account/')
    else:
        f = bsdUserToGroupForm(userid=object_id)
    variables = RequestContext(request, {
        'focused_tab' : 'account',
        'form' : f,
    })
    return render_to_response('account/bsdgroup2user_form.html', variables)

@login_required
def user2group_update2(request, object_id):
    if request.method == 'POST':
        f = bsdUserToGroupForm(object_id, request.POST)
        if f.is_valid():
            f.save()
            return HttpResponse(simplejson.dumps({"error": False, "message": _("%s successfully update.") % _("Groups")}), mimetype="application/json")
            #return render_to_response('account/bsdgroup2user_form_ok.html')
    else:
        f = bsdUserToGroupForm(userid=object_id)
    variables = RequestContext(request, {
        'url': reverse('account_bsduser_groups', kwargs={'object_id':object_id}),
        'form' : f,
    })
    return render_to_response('account/bsdgroup2user_form2.html', variables)
