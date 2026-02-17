from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.admin_login, name='admin_login'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('users/', views.user_management, name='user_management'),
    path('users/toggle-block/<int:user_id>/', views.toggle_block_user, name='toggle_block_user'),
    path('admin/search-users/', views.search_users, name='search_users'),
    path('logout/', views.admin_logout, name='admin_logout'),
    path('categories/', views.admin_category_list, name='admin_category_list'),
    # path('categories/add/', views.add_category, name='add_category'),
    # path('categories/edit/<int:pk>/', views.edit_category, name='edit_category'),
    # path('categories/delete/<int:pk>/', views.delete_category, name='delete_category'),



]
