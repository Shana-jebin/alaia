from django.urls import path
from . import views

urlpatterns = [
    path('shop/', views.shop_view, name='shop'),
    path('admin/categories/', views.admin_category_list, name='admin_category_list'),

]
