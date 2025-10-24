from aiohttp import web


class SiteManager:
    """
    Manages `aiohttp.web` sites. You can add multiple sites, start them, and later add more — those will start
    immediately.
    """

    def __init__(self):
        self.sites: list[tuple[type[web.BaseSite], tuple, dict]] = []
        self.runner: web.AppRunner | None = None

    async def add_site(self, klass: type[web.BaseSite], *args, **kwargs):
        """
        Adds a site to the manager. If `start_sites` has already been called, this site will be started immediately.

        :param klass: Site class
        :param args: Instantiation args (`aiohttp.web.AppRunner` will be prepended on `start_sites`).
        :param kwargs: Instantiation kwargs
        :return: None
        """
        self.sites.append((klass, args, kwargs))

        if self.runner:
            await self._start_site(klass, *args, **kwargs)

    async def start_sites(self, runner: web.AppRunner):
        """
        Starts all added sites. Any sites added afterward will be started automatically.

        :return: None
        """
        self.runner = runner

        for klass, args, kwargs in self.sites:
            await self._start_site(klass, *args, **kwargs)

    async def _start_site(self, klass: type[web.BaseSite], *args, **kwargs):
        site = klass(self.runner, *args, **kwargs)
        await site.start()
