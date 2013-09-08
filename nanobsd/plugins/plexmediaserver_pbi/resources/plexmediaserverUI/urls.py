from django.conf.urls import patterns, include, url

urlpatterns = patterns('',
     url(r'^plugins/plexmediaserver/(?P<plugin_id>\d+)/', include('plexmediaserverUI.freenas.urls')),
)
