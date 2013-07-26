from django.conf.urls import patterns, include, url

urlpatterns = patterns('',
     url(r'^plugins/firefly/(?P<plugin_id>\d+)/', include('fireflyUI.freenas.urls')),
)
