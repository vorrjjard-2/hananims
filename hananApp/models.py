from django.db import models
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from django.contrib.auth.models import User

class Ingredient(models.Model):
    PRIORITIES = [
        (1, 'High'),
        (2, 'Medium'),
        (3, 'Low')
    ]
    UNITS = [
        ('g', 'Grams'),
        ('pcs', 'Pieces')
    ]

    name = models.CharField(max_length=255)
    id = models.BigAutoField(primary_key=True)
    min_threshold = models.FloatField()
    quantity = models.FloatField()
    priority = models.IntegerField(choices=PRIORITIES)
    unit = models.CharField(max_length=10,choices=UNITS)
    price_per_unit = models.FloatField()

    def __str__(self):
        return self.name

class Dish(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    price = models.FloatField()

class RecipeDetails(models.Model):
    id = models.BigAutoField(primary_key=True)
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity_used = models.FloatField()

class Order(models.Model):
    id = models.BigAutoField(primary_key=True)
    date = models.DateTimeField(auto_now_add=True)

class OrderDetails(models.Model):
    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE)
    quantity = models.PositiveSmallIntegerField()

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('employee', 'Employee'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} ({self.role})"
