from django.core.exceptions import ValidationError as DjangoValidationError

from freenasUI.middleware.client import client

from middlewared.client.client import ValidationErrors as MiddlewareValidationErrors


class MiddlewareModelForm:
    key_prefix = NotImplemented
    is_singletone = NotImplemented
    middleware_plugin = NotImplemented

    def clean(self):
        try:
            self.__update(dry_run=True)
        except MiddlewareValidationErrors as e:
            django_errors = {}
            for error in e.errors:
                attribute = error.attribute
                attribute_prefix = "%s_update." % self.middleware_plugin
                if not attribute.startswith(attribute_prefix):
                    raise ValueError("Attribute name %r does not start with %r" % (attribute, attribute_prefix))
                attribute = attribute.split(".")[1]

                django_errors.setdefault(self.key_prefix + attribute, []).append(error.errmsg)
            raise DjangoValidationError(django_errors)

    def save(self):
        result = self.__update()

        self.instance = self._meta.model.objects.get(pk=result["id"])
        return self.instance

    def __update(self, *args, **kwargs):
        update = {
            k[len(self.key_prefix):]: v
            for k, v in self.cleaned_data.items()
            if k.startswith(self.key_prefix)
        }

        if self.is_singletone:
            args = (update,) + args
        else:
            args = (self.instance.id, update) + args

        with client as c:
            return c.call(f"{self.middleware_plugin}.update", *args, **kwargs)
