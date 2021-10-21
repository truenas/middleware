from middlewared.plugins.geom_.geom_cache import GeomCacheThread
from middlewared.service import Service


GCT = None  # global object representing geom cache thread


class Geom(Service):

    class Config:
        private = True

    def get_disks(self, from_cache=True):
        if not from_cache:
            self.invalidate_cache()
        return GCT.disks

    def get_xml(self, from_cache=True):
        if not from_cache:
            self.invalidate_cache()
        return GCT.xml

    def get_class_xml(self, class_name, from_cache=True):
        if not from_cache:
            self.invalidate_cache()

        if class_name.upper() in ('PART', 'MULTIPATH', 'DISK'):
            return GCT.xml.find(f'.//class[name="{class_name}"]') if GCT.xml else None

    def invalidate_cache(self):
        GCT.invalidate()

    def add_disk(self, disk):
        GCT.add(disk)

    def remove_disk(self, disk):
        GCT.remove(disk)


async def _event_system(middleware, event_type, args):
    global GCT
    if args['id'] == 'ready':
        if GCT is None or not GCT.is_alive():
            # start the geom cache thread
            GCT = GeomCacheThread().start()
    elif args['id'] == 'shutdown':
        if GCT is not None or GCT.is_alive():
            # stop the geom cache thread
            GCT.stop()
            GCT.join()


async def setup(middleware):
    middleware.event_subscribe('system', _event_system)
