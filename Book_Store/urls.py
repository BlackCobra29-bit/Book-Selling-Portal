"""
URL configuration for Book_Store project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from App.views import Index, Add_book, display_book, BookUpdateView, delete_book, PaymentSuccessView, PaymentCancelView, stripe_checkout, webhook_manager, user_login, dashboard, user_logout
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", Index, name="index"),
    path("admin-login/", user_login, name="login-page"),
    path("dashboard/", dashboard, name="app-dashboard"),
    path("add-books/", Add_book, name="add-book"),
    path("display-books/", display_book, name="display-book"),
    path('book/update/<int:pk>/', BookUpdateView.as_view(), name='update_book'),
    path('delete_book/<int:pk>/', delete_book, name='delete_book'),
    path("payment-success/", PaymentSuccessView.as_view(), name = "payment-success"),
    path('payment-cancel/', PaymentCancelView.as_view(), name='payment-cancel'),
    path("checkout/<int:book_id>", stripe_checkout, name="stripe-checkout"),
    path("stripe-webhook", webhook_manager, name = "webhook-manager"),
    path("logout", user_logout, name = "user-logout"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
