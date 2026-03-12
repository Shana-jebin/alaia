from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

app_name = "products" 

urlpatterns = [

    path('shop/', views.product_list, name='product_list'),
    path('api/variant/<int:variant_id>/', views.variant_data, name='variant_data'),
    path('api/review/<int:product_id>/', views.submit_review, name='submit_review'),
    path('<slug:slug>/', views.product_detail, name='product_detail'),
    

]
