from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import register_view, login_view, logout_view, dashboard, home, cart_view, about_view, contact_view, add_to_cart, remove_from_cart, update_quantity, orders_view, order_again_view, order_now, staff_dashboard, add_food
from .views import chatbot_view

urlpatterns = [
    path('', views.login_view, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('staff/dashboard', views.staff_dashboard, name='staff_dashboard'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('home/', views.home, name='home'),
    path('food/<int:food_id>/', views.food_detail, name='food_detail'),  # New URL for food detail
    path('cart/', views.cart_view, name='cart'),
    path('about/', views.about_view, name='about'),
    path('contact/', views.contact_view, name='contact'),
    path('add-to-cart/<int:food_id>/', views.add_to_cart, name='add_to_cart'),
    path('update-quantity/', views.update_quantity, name='update_quantity'),
    path('remove-from-cart/', views.remove_from_cart, name='remove_from_cart'),
    path('orders/', views.orders_view, name='orders'),
    path('order-again/<int:order_id>/', views.order_again_view, name='order_again'),
    path('staff/add/', views.add_food, name='add_food'),
    path('delete-food/<int:food_id>/', views.delete_food, name='delete_food'),
    path('order-now/<int:food_id>/', views.order_now, name='order_now'),
    path('order/all/', views.order_all, name='order_all'),
    path('place_order/', views.place_order, name='place_order'),
    path('order_success/', views.order_success, name='order_success'),
    path("staff/details/", views.staff_stats, name="staff_stats"),
    path("chatbot_view/", views.chatbot_view, name="chatbot_view"),
] 

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)