import re

from freenasUI.middleware.client import client, ClientException
from freenasUI.services.exceptions import ServiceFailed


def handle_middleware_validation(form, excep):
    for err in excep.errors:
        field_name = form.middleware_attr_map.get(err.attribute)
        error_message = err.errmsg
        if not field_name:
            field_name = err.attribute
            if form.middleware_attr_schema:
                if field_name.startswith(f'{form.middleware_attr_schema}.'):
                    field_name = field_name[len(form.middleware_attr_schema) + 1:]
            if form.middleware_attr_prefix:
                field_name = f'{form.middleware_attr_prefix}{field_name}'
            if (field_name not in form.fields and
                    len(field_name.split('.')) >= 3 and field_name.split('.')[-2].isdigit()):
                list_field_name = '.'.join(field_name.split('.')[:-2])
                if list_field_name in form.fields:
                    list_index = int(field_name.split('.')[-2])
                    field_name = list_field_name
                    error_message = repr(form.cleaned_data[field_name][list_index]) + f": {error_message}"
        if field_name not in form.fields:
            field_name = '__all__'

        if field_name not in form._errors:
            form._errors[field_name] = form.error_class([error_message])
        else:
            form._errors[field_name] += [error_message]


class MiddlewareModelForm:
    middleware_exclude_fields = []

    def save(self):
        result = self.__update()

        self.instance = self._meta.model.objects.get(pk=result["id"])
        return self.instance

    def middleware_clean(self, update):
        return update

    def middleware_prepare(self):
        update = {
            k[len(self.middleware_attr_prefix):]: v
            for k, v in self.cleaned_data.items()
            if (k.startswith(self.middleware_attr_prefix) and
                k[len(self.middleware_attr_prefix):] not in self.middleware_exclude_fields)
        }

        update = self.middleware_clean(update)

        return update

    def __update(self, *args, **kwargs):
        update = self.middleware_prepare()

        if self.is_singletone:
            args = (update,) + args
        else:
            args = (self.instance.id, update) + args

        with client as c:
            try:
                return c.call(f"{self.middleware_plugin}.update", *args, **kwargs)
            except ClientException as e:
                m = re.search(r'The (.+?) service failed to start', e.error)
                if m:
                    raise ServiceFailed(m.group(1), m.group(0))
                else:
                    raise
