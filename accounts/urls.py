from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('forgot-password/', views.forgot_password, name='forgot-password'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('logout/', views.logout_view, name='logout'),
    path('reset-password/', views.reset_password, name='reset-password'),
    path('forgot-otp/',views.forgot_otp,name='forgot-otp'),
    path('resend-forgot-otp/', views.resend_forgot_otp, name='resend_forgot_otp'),

    


]
