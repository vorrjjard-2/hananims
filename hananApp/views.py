from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.db import transaction
from .models import Ingredient, Dish, RecipeDetails, Order, OrderDetails
from django.db.models import F, FloatField, ExpressionWrapper
from .utils import priority_queue, insertion_sort, merge_sort
from django.contrib import messages
from django.core.exceptions import ValidationError
from collections import defaultdict, deque
from django.db.models import Sum

from django.db.models import Q, Prefetch

import heapq
from django.db.models import F, FloatField, ExpressionWrapper
from django.shortcuts import render
from django.db.models import Prefetch
from .models import Ingredient, Dish, RecipeDetails

from django.utils import timezone


def dashboard(request):
    # Fetch low-stock ingredients and calculate shortages
    ingredients = Ingredient.objects.annotate(
        shortage=ExpressionWrapper(
            1 - (F('quantity') / F('min_threshold')),
            output_field=FloatField()
        )
    ).filter(quantity__lt=F('min_threshold'))

    # Create a dictionary of shortages for quick lookup
    ingredient_shortages = {
        ingredient.id: 1 - (ingredient.quantity / ingredient.min_threshold)
        for ingredient in ingredients
    }

    # Determine sorting method for ingredients
    sorting = request.GET.get('sort_key', 'shortage')
    if sorting == 'shortage':
        sorted_ingredients = priority_queue(ingredients)
    elif sorting == 'priority':
        # First, sort strictly by shortage using priority_queue, then apply merge_sort by priority
        sorted_ingredients = priority_queue(ingredients)
        sorted_ingredients = merge_sort(sorted_ingredients, key="priority")
    else:
        sorted_ingredients = priority_queue(ingredients)  # Default to shortage sorting

    # Identify affected dishes
    low_stock_ingredient_ids = list(ingredient_shortages.keys())
    affected_dishes_query = Dish.objects.prefetch_related(
        Prefetch(
            'recipedetails_set',
            queryset=RecipeDetails.objects.filter(
                ingredient__id__in=low_stock_ingredient_ids
            ).select_related('ingredient'),
            to_attr='affected_details'
        )
    ).filter(recipedetails__ingredient__in=ingredients).distinct()

    # Create a list of affected dishes with relevant ingredient details and calculate urgency scores
    affected_dishes = []
    for dish in affected_dishes_query:
        urgency_score = 0  # Total urgency score for the dish
        for detail in dish.affected_details:
            shortage_factor = ingredient_shortages[detail.ingredient.id]
            urgency_score += shortage_factor * detail.ingredient.priority  # Weighted by ingredient priority
        affected_dishes.append({
            "name": dish.name,
            "affected_ingredients": [
                {
                    "name": detail.ingredient.name,
                    "shortage": ingredient_shortages[detail.ingredient.id],
                }
                for detail in dish.affected_details
            ],
            "urgency_score": urgency_score
        })

    # Sort affected dishes using bubble sort
    sorted_affected_dishes = insertion_sort(affected_dishes, 'urgency_score')

    context = {
        'ingredients': sorted_ingredients,
        'sort_key': sorting,
        'affected_dishes': sorted_affected_dishes,
    }

    return render(request, "hananApp/dashboard.html", context)

def replenish_ingredient(request):
    if request.method == 'GET':
        # Get parameters from the request
        ingredient_id = request.GET.get('ingredient_id')
        replenish_quantity = request.GET.get('replenish_quantity')

        try:
            replenish_quantity = float(replenish_quantity)
        except (ValueError, TypeError):
            messages.error(request, "Invalid replenish quantity. Please enter a valid number.")
            return redirect('dashboard')

        # Fetch the ingredient from the database
        ingredient = get_object_or_404(Ingredient, id=ingredient_id)

        # Update the ingredient's quantity
        old_quantity = ingredient.quantity
        ingredient.quantity += replenish_quantity
        ingredient.save()

        # Log the replenishment (you can add database logging here if required)
        print(f"Replenished {ingredient.name} (ID: {ingredient_id}): {old_quantity} -> {ingredient.quantity} (added {replenish_quantity} units).")

        # Add a success message
        messages.success(request, f"Successfully replenished {ingredient.name} by {replenish_quantity} {ingredient.unit}.")
        
    return redirect('dashboard')

def orders(request):
    orders = Order.objects.prefetch_related('orderdetails_set__dish').order_by('-date')

    today = timezone.now().date()
    todays_sales = (
        OrderDetails.objects
        .filter(order__date__date=today)
        .values('dish__name')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')
    )

    context = {
        'orders': orders,
        'todays_sales': todays_sales,
        'today': today
    }
    return render(request, 'hananApp/orders.html', context)

from django.db import transaction
from django.shortcuts import render, redirect
from django.core.exceptions import ValidationError
from .models import Dish, Order, OrderDetails, Ingredient, RecipeDetails

def add_order(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Create a new order
                order = Order.objects.create()

                # Track required ingredient updates
                ingredient_usage = {}
                dishes_ordered = False  # Flag to check if any dish was ordered

                for dish_id, quantity in request.POST.items():
                    if dish_id.startswith('dish_') and quantity.isdigit() and int(quantity) > 0:
                        dishes_ordered = True  # At least one dish was ordered
                        dish_id = dish_id.split('_')[1]
                        dish = Dish.objects.get(id=dish_id)
                        quantity = int(quantity)

                        # Add order details
                        OrderDetails.objects.create(order=order, dish=dish, quantity=quantity)

                        # Calculate ingredient usage for the dish
                        recipe_details = RecipeDetails.objects.filter(dish=dish)
                        for recipe in recipe_details:
                            if recipe.ingredient.id not in ingredient_usage:
                                ingredient_usage[recipe.ingredient.id] = 0
                            ingredient_usage[recipe.ingredient.id] += recipe.quantity_used * quantity

                if not dishes_ordered:
                    raise ValidationError("No dishes were ordered. Please select at least one dish.")

                # Update ingredient quantities
                for ingredient_id, total_usage in ingredient_usage.items():
                    ingredient = Ingredient.objects.get(id=ingredient_id)
                    if ingredient.quantity < total_usage:
                        raise ValidationError(
                            f"Insufficient stock for ingredient '{ingredient.name}'."
                        )
                    ingredient.quantity -= total_usage
                    ingredient.save()

                return redirect('orders')  # Redirect to orders page
        except ValidationError as e:
            # Handle validation errors
            return render(request, 'hananApp/add_order.html', {
                'dishes': Dish.objects.all(),
                'error': str(e)
            })

    # For GET requests, render the form with all dishes
    dishes = Dish.objects.all()
    return render(request, 'hananApp/add_order.html', {'dishes': dishes})


def add_dish(request):
    if request.method == "POST":
        dish_name = request.POST.get("name")
        ingredient_ids = []

        # Collect all selected ingredient IDs
        for key, value in request.POST.items():
            if key.startswith("ingredient_"):
                ingredient_ids.append(value)

        # Check for duplicates
        if len(ingredient_ids) != len(set(ingredient_ids)):
            messages.error(request, "Duplicate ingredients are not allowed.")
            return redirect("add_dish")  # Replace with the actual redirect URL

        # Process form and save the dish
        dish = Dish(name=dish_name)
        dish.save()

        # Save the ingredients associated with this dish
        for i, ingredient_id in enumerate(ingredient_ids):
            ingredient = Ingredient.objects.get(id=ingredient_id)
            quantity = request.POST.get(f"quantity_{i + 1}")
            RecipeDetails.objects.create(dish=dish, ingredient=ingredient, quantity_used=quantity)

        messages.success(request, "Dish added successfully!")
        return redirect("dishes")  # Replace with the actual redirect URL

    # Return the template with ingredients
    ingredients = Ingredient.objects.all()
    return render(request, "hananApp/add_dish.html", {"ingredients": ingredients})

def add_ingredient(request):
    if request.method == "POST":
        reqname = request.POST.get("name")
        print(f"Ingredient Name Received: {reqname}")

        if not reqname or not all(c.isalpha() or c.isspace() for c in reqname):
            messages.error(request, "Name cannot be empty and must be alphabetic.")
            return render(request, 'hananApp/add_ingredient.html', {'form_data': request.POST})

        if Ingredient.objects.filter(name=reqname).exists():
            messages.error(request, "This ingredient already exists.")
            return render(request, 'hananApp/add_ingredient.html', {'form_data': request.POST})

        try:
            reqquantity = float(request.POST.get("quantity"))
            if reqquantity <= 0:
                messages.error(request, "Quantity must be greater than zero.")
                return render(request, 'hananApp/add_ingredient.html', {'form_data': request.POST})
        except ValueError:
            messages.error(request, "Quantity must be a valid float.")
            return render(request, 'hananApp/add_ingredient.html', {'form_data': request.POST})

        try:
            reqmin_threshold = float(request.POST.get("minThreshold"))
            print(reqmin_threshold)
            if reqmin_threshold <= 0:
                messages.error(request, "Minimum threshold must be greater than zero.")
                return render(request, 'hananApp/add_ingredient.html', {'form_data': request.POST})
        except ValueError:
            messages.error(request, "Minimum threshold must be a valid float.")
            return render(request, 'hananApp/add_ingredient.html', {'form_data': request.POST})

        try:
            price_per_unit = float(request.POST.get('price_per_unit'))
            if price_per_unit <= 0:
                messages.error(request, "Price per unit must be greater than 0.")
                return render(request, 'hananApp/add_ingredient.html', {'form_data' : request.POST})
        except ValueError:
            messages.error(request, "Price must be a valid float.")
            return render(request, 'hananApp/add_ingredient.html', {'form_data' : request.POST})


        requnit = request.POST.get("unit")
        if not requnit:
            messages.error(request, "Unit must be selected.")
            return render(request, 'hananApp/add_ingredient.html', {'form_data': request.POST})
        reqpriority = int(request.POST.get("priority"))
        print(reqpriority)
        if not reqpriority:
            messages.error(request, "Priority must be selected.")
            return render(request, 'hananApp/add_ingredient.html', {'form_data': request.POST})
        
        try:
            ingredient = Ingredient.objects.create(
                name=reqname,
                quantity=reqquantity,
                min_threshold=reqmin_threshold,
                unit=requnit,
                priority=reqpriority,
                price_per_unit=price_per_unit
            )
            messages.success(request, "Ingredient added successfully!")
            print(f"Ingredient {ingredient} created successfully.")
            return redirect('add_ingredient')
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return render(request, 'hananApp/add_ingredient.html', {'form_data': request.POST})

    return render(request, 'hananApp/add_ingredient.html')

def view_ingredients(request):
    ingredients = Ingredient.objects.all()
    return render(request, 'hananApp/view_ingredients.html', {'ingredients':ingredients})

def dishes(request):
    # Fetch all dishes along with their related ingredients
    dishes = Dish.objects.prefetch_related('recipedetails_set__ingredient')
    context = {
        'dishes':dishes
    }

    return render(request, 'hananApp/dishes.html', context)

def update_inventory(request):
    if request.method == 'POST':
        entries = request.POST.getlist('ingredient')
        actions = request.POST.getlist('action')
        amounts = request.POST.getlist('amount')
        units = request.POST.getlist('unit')
        costs = request.POST.getlist('cost')

        for i in range(len(entries)):
            try:
                ingredient = Ingredient.objects.get(pk=entries[i])
                amount = float(amounts[i])
                cost = float(costs[i])
                action = actions[i]

                if action == 'add':
                    ingredient.quantity += amount
                elif action == 'reduce':
                    ingredient.quantity = max(0, ingredient.quantity - amount)

                ingredient.save()

            except Exception as e:
                print(f"Error processing row {i}: {e}")
                continue

        return redirect('dashboard') 

    ingredients = Ingredient.objects.all()
    context = {'ingredients': ingredients, 'now': timezone.now()}
    return render(request, 'hananApp/update_inventory.html', context)

def generate_report(request):

    report_items = []

    if request.method == "POST":

        start_date = "2024-11-17"
        end_date = "2024-11-24"

        start_date = request.POST.get('start_date', start_date)
        end_date = request.POST.get('end_date', end_date)
        report_items = request.POST.getlist('report_items')  
        
        if 'current_inventory_level' in report_items:
            pass
        if 'low_stock_categorization' in report_items:
            pass
        if 'dish_sales_and_tally' in report_items:
            pass
        if 'financial_details' in report_items:
            pass
        if 'inventory_usage' in report_items:
            pass

    context =  {
        'start_date': start_date,
        'end_date': end_date,
        'report_items': report_items  
    }
    return render(request, 'hananApp/report.html', context)