from django.contrib import admin
from .models import Ingredient, Dish, RecipeDetails, Order, OrderDetails


admin.site.register(Ingredient)
admin.site.register(Dish)
admin.site.register(RecipeDetails)
admin.site.register(Order)
admin.site.register(OrderDetails)
