from django.db import models
from django.db.models.base import ModelBase

class FreeAdminWrapper(object):

    create_modelform = None
    edit_modelform = None
    exclude_fields = []
    deletable = True
    menu_child_of = None

    object_filters = {}
    object_num = -1

    icon_model = None
    icon_object = None
    icon_add = None
    icon_view = None

    def __init__(self, c=None):

        if c is None:
            return None
        obj = c()
        for i in dir(obj):
            if not i.startswith("__"):
                if not hasattr(self, i):
                    raise Exception("The attribute '%s' is a not valid in FreeAdmin" % i)
                self.__setattr__(i, getattr(obj, i))

class FreeAdminBase(ModelBase):
    def __new__(cls, name, bases, attrs):
        new_class = ModelBase.__new__(cls, name, bases, attrs)
        if hasattr(new_class, 'FreeAdmin'):
            new_class.add_to_class('_admin', FreeAdminWrapper(new_class.FreeAdmin))
        else:
            new_class.add_to_class('_admin', FreeAdminWrapper())

        return new_class

class Model(models.Model):
    __metaclass__ = FreeAdminBase

    class Meta:
        abstract = True
