from django.db import models

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