"""
URL configuration for hananIMS project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
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
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.login_view, name="login_view"),
    path('dashboard/', views.dashboard, name="dashboard"),
    path('replenish-ingredient/', views.replenish_ingredient, name='replenish_ingredient'),
    path('dishes', views.dishes, name='dishes'),
    path('orders', views.orders, name='orders'),
    path('add_order', views.add_order, name='add_order'),
    path('add_dish', views.add_dish, name='add_dish'),
    path('add_ingredient', views.add_ingredient, name="add_ingredient"),
    path('view_ingredients', views.view_ingredients, name='view_ingredients'),
    path('update_inventory', views.update_inventory, name="update_inventory"),
    path('generate_report', views.generate_report, name="generate_report"),
    path('report', views.report, name="report"),
    path('edit_dish/<int:dish_id>/', views.edit_dish, name='edit_dish'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    path('delete-dish/<int:dish_id>/', views.delete_dish, name='delete_dish'),
]
