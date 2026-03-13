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
    path('product/<int:pk>/restore/', views.restore_product, name='restore_product'),
    path('product/<int:pk>/toggle-status/', views.product_toggle_status, name='toggle_status'),
    path('product/upload-image/', views.product_upload_image, name='upload_image'),


    path('brands/', views.brand_list, name='brand_list'),
    path('brands/create/', views.brand_create, name='brand_create'),
    path('brands/<int:pk>/edit/', views.brand_edit, name='brand_edit'),
    path('brands/<int:pk>/delete/', views.brand_delete, name='brand_delete'),
    path('brands/restore/<int:pk>/', views.brand_restore, name='brand_restore'),

    
    path('coupons/',                 views.coupon_list,   name='admin_coupon_list'),
    path('coupons/create/',          views.coupon_create, name='admin_coupon_create'),
    path('coupons/<int:pk>/edit/',   views.coupon_edit,   name='admin_coupon_edit'),
    path('coupons/<int:pk>/toggle/', views.coupon_toggle, name='admin_coupon_toggle'),
    path('coupons/<int:pk>/delete/', views.coupon_delete, name='admin_coupon_delete'),

    path('orders/', views.admin_order_list, name='admin_order_list'),
    path('orders/<str:order_id>/', views.admin_order_detail, name='admin_order_detail'),
    path('orders/<str:order_id>/status/', views.admin_order_status, name='admin_order_status'),

    path('reviews/',                  views.review_list,    name='admin_review_list'),
    path('reviews/<int:review_id>/approve/', views.review_approve, name='admin_review_approve'),
    path('reviews/<int:review_id>/reject/',  views.review_reject,  name='admin_review_reject'),
    path('reviews/<int:review_id>/delete/',  views.review_delete,  name='admin_review_delete'),

    path('inventory/', views.admin_inventory, name='admin_inventory'),
    path('inventory/<int:variant_id>/update/', views.admin_update_stock, name='admin_update_stock'),

    path('logout/', views.admin_logout, name='admin_logout'),
    


    
]
