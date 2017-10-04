from freenasUI.middleware.client import client


class MiddlewareModelForm:

    def save(self):
        result = self.__update()

        self.instance = self._meta.model.objects.get(pk=result["id"])
        return self.instance

    def middleware_clean(self):
        update = {
            k[len(self.middleware_attr_prefix):]: v
            for k, v in self.cleaned_data.items()
            if k.startswith(self.middleware_attr_prefix)
        }
        return update

    def __update(self, *args, **kwargs):

        update = self.middleware_clean()

        if self.is_singletone:
            args = (update,) + args
        else:
            args = (self.instance.id, update) + args

        with client as c:
            return c.call(f"{self.middleware_plugin}.update", *args, **kwargs)
