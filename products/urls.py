from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

app_name = "products" 

urlpatterns = [
    path('shop/', views.product_list, name='product_list'),
    path('<slug:slug>/',                       views.product_detail, name='product_detail'),
    path('api/variant/<int:variant_id>/',      views.variant_data,   name='variant_data'),
    path('api/review/<int:product_id>/',       views.submit_review,  name='submit_review'),

    path('cart/', views.cart_view, name='cart'),
    path('add-to-cart/<int:variant_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:item_id>/<str:action>/', views.update_cart_quantity, name='update_cart'),
    

]
