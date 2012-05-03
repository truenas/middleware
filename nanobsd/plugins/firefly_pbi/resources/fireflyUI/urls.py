from django.conf.urls.defaults import patterns, include, url

urlpatterns = patterns('',
     url(r'^plugins/firefly/', include('fireflyUI.freenas.urls')),
)
