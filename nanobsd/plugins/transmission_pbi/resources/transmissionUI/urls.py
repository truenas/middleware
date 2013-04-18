from django.conf.urls.defaults import patterns, include, url

urlpatterns = patterns('',
     url(r'^plugins/transmission/(?P<plugin_id>\d+)/', include('transmissionUI.freenas.urls')),
)
