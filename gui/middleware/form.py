from freenasUI.middleware.client import client


def handle_middleware_validation(form, excep):
    for err in excep.errors:
        field_name = form.middleware_attr_map.get(err.attribute)
        if not field_name:
            field_name = err.attribute
            if form.middleware_attr_schema:
                if field_name.startswith(f'{form.middleware_attr_schema}.'):
                    field_name = field_name[len(form.middleware_attr_schema) + 1:]
            if form.middleware_attr_prefix:
                field_name = f'{form.middleware_attr_prefix}{field_name}'
        if field_name in form.fields:
            form._errors[field_name] = form.error_class([err.errmsg])
        else:
            if '__all__' not in form._errors:
                form._errors['__all__'] = form.error_class([err.errmsg])
            else:
                form._errors['__all__'] += [err.errmsg]


class MiddlewareModelForm:

    def save(self):
        result = self.__update()

        self.instance = self._meta.model.objects.get(pk=result["id"])
        return self.instance

    def __update(self, *args, **kwargs):
        update = {
            k[len(self.middleware_attr_prefix):]: v
            for k, v in self.cleaned_data.items()
            if k.startswith(self.middleware_attr_prefix)
        }

        if self.is_singletone:
            args = (update,) + args
        else:
            args = (self.instance.id, update) + args

        with client as c:
            return c.call(f"{self.middleware_plugin}.update", *args, **kwargs)
