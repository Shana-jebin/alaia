from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [

    # ── Checkout ──────────────────────────────────────────────────
    path('checkout/',                       views.checkout,              name='checkout'),
    path('apply-coupon/',                   views.apply_coupon,          name='apply_coupon'),
    path('place/',                          views.place_order,           name='place_order'),
    path('success/<str:order_id>/',         views.order_success,         name='order_success'),

    # ── Razorpay ──────────────────────────────────────────────────
    path('payment/<str:order_id>/',         views.razorpay_payment,      name='razorpay_payment'),
    path('razorpay/callback/',              views.razorpay_callback,     name='razorpay_callback'),
    path('payment-failed/<str:order_id>/',  views.payment_failed,        name='payment_failed'),
    path('retry-payment/<str:order_id>/',   views.retry_payment,         name='retry_payment'),

    # ── Orders ────────────────────────────────────────────────────
    path('my-orders/',                      views.order_list,            name='order_list'),
    path('my-orders/<str:order_id>/',       views.order_detail,          name='order_detail'),
    path('cancel/<str:order_id>/',          views.cancel_order,          name='cancel_order'),
    path('cancel/<str:order_id>/item/<int:item_id>/', views.cancel_item, name='cancel_item'),
    path('return/<str:order_id>/',                                        views.return_order,  name='return_order'),
    path('return/<str:order_id>/item/<int:item_id>/',                     views.return_item,   name='return_item'),
    path('invoice/<str:order_id>/',         views.download_invoice,      name='download_invoice'),

    # ── Wallet ────────────────────────────────────────────────────
    path('wallet/',                         views.wallet_page,           name='wallet'),
    path('wallet/add-money/', views.wallet_add_money, name='wallet_add_money'),

    # ── Wishlist ──────────────────────────────────────────────────
    path('wishlist/',                                   views.wishlist_page,         name='wishlist'),
    path('wishlist/status/',                            views.wishlist_status,       name='wishlist_status'),
    path('wishlist/toggle/<int:product_id>/',           views.toggle_wishlist,       name='toggle_wishlist'),
    path('wishlist/remove/<int:product_id>/',           views.remove_from_wishlist,  name='remove_from_wishlist'),
    path('wishlist/move-to-cart/<int:product_id>/',     views.move_to_cart,          name='move_to_cart'),

    # ── Cart ──────────────────────────────────────────────────────
    path('cart/',                                       views.cart_view,             name='cart'),
    path('add-to-cart/<int:variant_id>/',               views.add_to_cart,           name='add_to_cart'),
    path('cart/update/<int:item_id>/<str:action>/',     views.update_cart_quantity,  name='update_cart'),
]