
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import logout_view




urlpatterns = [
    path('admin-secret/', admin.site.urls), 
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')), 
    path('accounts/', include('allauth.urls')),
    path('admin-panel/', include('adminpanel.urls')),
    path('profile/', include('user_profile.urls')),
    path('products/', include('products.urls')),
    path('orders/',include('orders.urls')),
    path('logout/', logout_view, name='logout'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


