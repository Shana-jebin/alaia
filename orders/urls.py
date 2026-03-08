from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('checkout/',                                  views.checkout,        name='checkout'),
    path('apply-coupon/',                              views.apply_coupon,    name='apply_coupon'),
    path('place/',                                     views.place_order,     name='place_order'),
    path('success/<str:order_id>/',                    views.order_success,   name='order_success'),
    path('my-orders/',                                 views.order_list,      name='order_list'),
    path('my-orders/<str:order_id>/',                  views.order_detail,    name='order_detail'),
    path('cancel/<str:order_id>/',                     views.cancel_order,    name='cancel_order'),
    path('cancel/<str:order_id>/item/<int:item_id>/',  views.cancel_item,     name='cancel_item'),
    path('return/<str:order_id>/',                     views.return_order,    name='return_order'),
    path('invoice/<str:order_id>/',                    views.download_invoice,name='download_invoice'),
]