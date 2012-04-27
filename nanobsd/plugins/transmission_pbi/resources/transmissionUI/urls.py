from django.conf.urls.defaults import patterns, include, url

urlpatterns = patterns('',
     url(r'^plugins/transmission/', include('transmissionUI.freenas.urls')),
)
