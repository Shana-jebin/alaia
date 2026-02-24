from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.admin_login, name='admin_login'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('users/', views.user_management, name='user_management'),
    path('users/toggle-block/<int:user_id>/', views.toggle_block_user, name='toggle_block_user'),
    path('search-users/', views.search_users, name='search_users'),
    path('categories/', views.admin_category_list, name='admin_category_list'),
    path('category/edit/<int:category_id>/', views.admin_category_edit, name='admin_category_edit'),
    path('category/delete/<int:category_id>/',views.admin_category_delete,name='admin_category_delete'),

    path('product/', views.product_list, name='list'),
    path('product/add/', views.product_add, name='add'),
    path('product/<int:pk>/edit/', views.product_edit, name='edit'),
    path('product/<int:pk>/soft-delete/', views.product_soft_delete, name='soft_delete'),
    path('product/<int:pk>/toggle-status/', views.product_toggle_status, name='toggle_status'),
    path('product/upload-image/', views.product_upload_image, name='upload_image'),

    path('brands/', views.brand_list, name='brand_list'),
    path('brands/create/', views.brand_create, name='brand_create'),
    path('brands/<int:pk>/edit/', views.brand_edit, name='brand_edit'),
    path('brands/<int:pk>/delete/', views.brand_delete, name='brand_delete'),
    path('brands/restore/<int:pk>/', views.brand_restore, name='brand_restore'),


]
