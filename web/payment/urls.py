from django.urls import path
from . import views

urlpatterns = [
    path('payment/', views.payment_page_view, name='payment_page'),
    path('payment/checkout/', views.create_checkout_session, name='create_checkout_session'),
    path('payment/success/', views.payment_success_view, name='payment_success'),
    path('payment/cancel/', views.payment_cancel_view, name='payment_cancel'),
    path('payment/error/', views.payment_error_view, name='payment_error'),
]