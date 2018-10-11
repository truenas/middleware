import json

from django.core.exceptions import FieldDoesNotExist
from django.db.models import Model

from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.models.fields import DictField, ListField
from freenasUI.middleware.client import client, ClientException
from freenasUI.services.exceptions import ServiceFailed


def handle_middleware_validation(form, excep):
    for err in excep.errors:
        field_name = form.middleware_attr_map.get(err.attribute)
        error_message = err.errmsg
        if not field_name and '.' in err.attribute:
            field_name = form.middleware_attr_map.get(err.attribute.split('.', 1)[-1])
        if not field_name:
            field_name = err.attribute
            if form.middleware_attr_schema:
                schema = f'{form.middleware_attr_schema}_{form._middleware_action}'
                if field_name.startswith(f'{schema}.'):
                    field_name = field_name[len(schema) + 1:]
            if form.middleware_attr_prefix:
                field_name = f'{form.middleware_attr_prefix}{field_name}'
            if (field_name not in form.fields and
                    len(field_name.split('.')) >= 3 and field_name.split('.')[-2].isdigit()):
                list_field_name = '.'.join(field_name.split('.')[:-2])
                if list_field_name in form.fields:
                    list_index = int(field_name.split('.')[-2])
                    field_name = list_field_name
                    if isinstance(form.cleaned_data[field_name], list):
                        list_ = form.cleaned_data[field_name]
                    else:
                        list_ = form.cleaned_data[field_name].split()
                    error_message = repr(list_[list_index]) + f": {error_message}"
        if field_name not in form.fields:
            field_name = '__all__'

        if field_name not in form._errors:
            form._errors[field_name] = form.error_class([error_message])
        else:
            form._errors[field_name] += [error_message]


class MiddlewareModelForm:
    middleware_attr_prefix = NotImplemented
    middleware_attr_schema = NotImplemented
    middleware_plugin = NotImplemented
    middleware_job = False
    is_singletone = NotImplemented

    middleware_exclude_fields = []

    def save(self):
        result = self.__save()

        self.instance = self._meta.model.objects.get(pk=result["id"])
        return self.instance

    def middleware_clean(self, data):
        return data

    def middleware_prepare(self):
        data = {
            k[len(self.middleware_attr_prefix):]: self.__middleware_prepare_value(k, v)
            for k, v in self.cleaned_data.items()
            if (k.startswith(self.middleware_attr_prefix) and
                k[len(self.middleware_attr_prefix):] not in self.middleware_exclude_fields)
        }

        data = self.middleware_clean(data)

        return data

    def __middleware_prepare_value(self, k, v):
        if isinstance(v, Model):
            return v.id

        try:
            field = self.instance._meta.get_field(k)
        except FieldDoesNotExist:
            pass
        else:
            if isinstance(field, (DictField, ListField)) and isinstance(v, (str, bytes, bytearray)):
                return json.loads(v)

        return v

    def __save(self, *args, **kwargs):
        data = self.middleware_prepare()

        if self.instance.id:
            self._middleware_action = "update"

            if self.is_singletone:
                args = (data,) + args
            else:
                args = (self.instance.id, data) + args
        else:
            self._middleware_action = "create"

            args = (data,) + args

        if self.middleware_job:
            kwargs['job'] = True

        with client as c:
            try:
                return c.call(f"{self.middleware_plugin}.{self._middleware_action}", *args, **kwargs)
            except ClientException as e:
                if e.errno == ClientException.ESERVICESTARTFAILURE:
                    raise ServiceFailed(e.extra[0], e.error)
                else:
                    raise

    def delete(self, request=None, events=None, **kwargs):
        with client as c:
            c.call(f"{self.middleware_plugin}.delete", self.instance.id)

        fname = str(type(self).__name__)
        appPool.hook_form_delete(fname, self, request, events)
