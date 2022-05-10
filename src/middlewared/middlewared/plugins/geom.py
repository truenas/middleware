from middlewared.service import Service
from middlewared.plugins.geom_.cache import GeomCachedObjects

GCACHE = GeomCachedObjects()


class GeomCache(Service):

    class Config:
        namespace = 'geom.cache'
        private = True

    def get_disks(self):
        return GCACHE.get_disks()

    def get_multipath(self):
        return GCACHE.get_multipath()

    def get_topology(self):
        return GCACHE.get_topology()

    def get_xml(self):
        return GCACHE.get_xml()

    def get_class_xml(self, class_name):
        return GCACHE.get_xml(xml_class=class_name.upper())

    def invalidate(self):
        GeomCachedObjects.cache.fget.cache_clear()

    def remove_disk(self, disk):
        pass

    def get_devices_topology(self):
        return GCACHE.get_topology()
