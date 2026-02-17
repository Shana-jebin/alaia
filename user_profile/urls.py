from django.urls import path
from . import views

urlpatterns = [
    path("", views.profile_view, name="profile"),
    path('verify-otp/', views.verify_email_otp, name='verify_email_otp'),
    path("resend-otp/", views.resend_otp, name="resend_otp"),
    path("addresses/", views.address_list, name="address_list"),
    path("profile/addresses/add/", views.add_address, name="add_address"),
    path('address/<int:id>/edit/', views.edit_address, name='edit_address'),
    path('address/<int:id>/delete/', views.delete_address, name='delete_address'),
    path('set-default-address/<int:id>/', views.set_default_address, name='set_default_address'),



]
