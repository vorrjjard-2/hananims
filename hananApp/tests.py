from django.test import TestCase, Client
from django.urls import reverse
from .models import Ingredient, Dish, RecipeDetails, Order, OrderDetails
from django.contrib.messages import get_messages

class HananAppTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.ingredient1 = Ingredient.objects.create(name="Salt", quantity=5, min_threshold=10, unit="g", priority=2)
        self.ingredient2 = Ingredient.objects.create(name="Sugar", quantity=15, min_threshold=10, unit="g", priority=1)
        self.dish = Dish.objects.create(name="Sweet Dish")
        RecipeDetails.objects.create(dish=self.dish, ingredient=self.ingredient1, quantity_used=2)

    def test_dashboard_view(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('ingredients', response.context)
        self.assertIn('affected_dishes', response.context)

    def test_replenish_ingredient_valid(self):
        url = reverse('replenish_ingredient') + f'?ingredient_id={self.ingredient1.id}&replenish_quantity=10'
        response = self.client.get(url)
        self.ingredient1.refresh_from_db()
        self.assertEqual(self.ingredient1.quantity, 15)
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Successfully replenished" in str(m) for m in messages))

    def test_replenish_ingredient_invalid_quantity(self):
        url = reverse('replenish_ingredient') + f'?ingredient_id={self.ingredient1.id}&replenish_quantity=abc'
        response = self.client.get(url)
        self.assertRedirects(response, reverse('dashboard'))

    def test_orders_view(self):
        response = self.client.get(reverse('orders'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('orders', response.context)

    def test_add_order_valid(self):
        url = reverse('add_order')
        post_data = {
            f'dish_{self.dish.id}': '2'
        }
        response = self.client.post(url, post_data)
        self.assertRedirects(response, reverse('orders'))
        self.ingredient1.refresh_from_db()
        self.assertEqual(self.ingredient1.quantity, 1)

    def test_add_order_insufficient_stock(self):
        self.ingredient1.quantity = 2  
        self.ingredient1.save()
        url = reverse('add_order')
        post_data = {
            f'dish_{self.dish.id}': '2'
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Insufficient stock")

    def test_add_dish_with_duplicate_ingredients(self):
        url = reverse('add_dish')
        post_data = {
            "name": "Test Dish",
            "ingredient_1": str(self.ingredient1.id),
            "ingredient_2": str(self.ingredient1.id),  # Duplicate
            "quantity_1": "2",
            "quantity_2": "3"
        }
        response = self.client.post(url, post_data)
        self.assertRedirects(response, reverse('add_dish'))
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Duplicate ingredients" in str(m) for m in messages))

    def test_add_ingredient_valid(self):
        response = self.client.post(reverse('add_ingredient'), {
            "name": "Butter",
            "quantity": "5",
            "minThreshold": "2",
            "unit": "g",
            "priority": "3"
        })
        self.assertEqual(Ingredient.objects.filter(name="Butter").count(), 1)
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Ingredient added successfully" in str(m) for m in messages))

    def test_add_ingredient_invalid_name(self):
        response = self.client.post(reverse('add_ingredient'), {
            "name": "123Butter",
            "quantity": "5",
            "minThreshold": "2",
            "unit": "g",
            "priority": "3"
        })
        self.assertContains(response, "Name cannot be empty and must be alphabetic.")

    def test_view_ingredients(self):
        response = self.client.get(reverse('view_ingredients'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('ingredients', response.context)

    def test_dishes_view(self):
        response = self.client.get(reverse('dishes'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('dishes', response.context)