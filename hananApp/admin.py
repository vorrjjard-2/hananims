from django.contrib import admin
from .models import Ingredient, Dish, RecipeDetails, Order, OrderDetails, UserProfile


admin.site.register(Ingredient)
admin.site.register(Dish)
admin.site.register(RecipeDetails)
admin.site.register(Order)
admin.site.register(OrderDetails)
admin.site.register(UserProfile)