from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
from django.db import transaction
from .models import Ingredient, Dish, RecipeDetails, Order, OrderDetails
from django.db.models import F, FloatField, ExpressionWrapper
from .utils import priority_queue, insertion_sort, merge_sort
from django.contrib import messages
from django.core.exceptions import ValidationError
from collections import defaultdict, deque
from django.db.models import Sum

from django.db.models import Q, Prefetch

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

import heapq
from django.db.models import F, FloatField, ExpressionWrapper
from django.shortcuts import render
from django.db.models import Prefetch
from .models import Ingredient, Dish, RecipeDetails

from django.utils import timezone
from django.contrib.auth import login
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User

def login_view(request):
    logger.info("Entered view: login_view")
    error = ""
    
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            role = user.userprofile.role

            if role == 'admin':
                return redirect('dashboard')
            else:
                return redirect('dashboard')
        else:
            error = "Invalid username or password."

    return render(request, 'hananApp/login.html', {"error": error})

def dashboard(request):
    logger.info("Entered view: dashboard")
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
    logger.info("Entered view: replenish_ingredient")
    if request.user.userprofile.role != 'admin':
        return HttpResponse("""
            <html>
                <head>
                    <meta http-equiv="refresh" content="2; url=/employee-dashboard/" />
                </head>
                <body style="font-family: sans-serif; text-align: center; padding: 40px;">
                    <h2>You are not authorized to view this page.</h2>
                    <p>Redirecting you back in 2 seconds...</p>
                </body>
            </html>
        """)
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
    logger.info("Entered view: orders")
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
    logger.info("Entered view: add_order")
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


def delete_dish(request, dish_id):
    logger.info("Entered view: delete_dish")
    if request.user.userprofile.role != 'admin':
        messages.error(request, "You are not authorized to delete dishes.")
        return redirect('dishes')

    dish = get_object_or_404(Dish, id=dish_id)
    dish.delete()
    messages.success(request, "Dish deleted successfully.")
    return redirect('dishes')

def add_dish(request):
    logger.info("Entered view: add_dish")
    if request.user.userprofile.role != 'admin':
        return HttpResponse("""
            <html>
                <head>
                    <meta http-equiv="refresh" content="2; url=/dashboard/" />
                </head>
                <body style="font-family: sans-serif; text-align: center; padding: 40px;">
                    <h2>You are not authorized to view this page.</h2>
                    <p>Redirecting you back in 2 seconds...</p>
                </body>
            </html>
        """)
    

    if request.method == "POST":
        dish_name = request.POST.get("name")
        dish_price = request.POST.get("price")  # Grab the dish price
        ingredient_ids = []

        if Dish.objects.filter(name__iexact=dish_name).exists():
            messages.error(request, "A dish with this name already exists.")
            return redirect("add_dish")

        # Collect all selected ingredient IDs
        for key, value in request.POST.items():
            if key.startswith("ingredient_"):
                ingredient_ids.append(value)

        # Check for duplicates
        if len(ingredient_ids) != len(set(ingredient_ids)):
            messages.error(request, "Duplicate ingredients are not allowed.")
            return redirect("add_dish")  # Replace with the actual redirect URL

        # Process form and save the dish
        dish = Dish(name=dish_name, price=dish_price)  # Save the price along with the name
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
    logger.info("Entered view: add_ingredient")
    if request.user.userprofile.role != 'admin':
        return HttpResponse("""
            <html>
                <head>
                    <meta http-equiv="refresh" content="2; url=/dashboard/" />
                </head>
                <body style="font-family: sans-serif; text-align: center; padding: 40px;">
                    <h2>You are not authorized to view this page.</h2>
                    <p>Redirecting you back in 2 seconds...</p>
                </body>
            </html>
        """)
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
    logger.info("Entered view: view_ingredients")
    ingredients = Ingredient.objects.all()
    return render(request, 'hananApp/view_ingredients.html', {'ingredients':ingredients})

def dishes(request):
    logger.info("Entered view: dishes")
    # Fetch all dishes and their related ingredients in one query for efficiency
    dishes = Dish.objects.prefetch_related('recipedetails_set__ingredient')

    # Dynamically calculate estimated cost for each dish
    for dish in dishes:
        total_cost = 0.0
        for rd in dish.recipedetails_set.all():
            total_cost += rd.quantity_used * rd.ingredient.price_per_unit 
        dish.estimated_cost = round(total_cost, 2)  # Attach as a temporary attribute

    context = {
        'dishes': dishes
    }

    return render(request, 'hananApp/dishes.html', context)

def update_inventory(request):
    logger.info("Entered view: update_inventory")
    if request.user.userprofile.role != 'admin':
        return HttpResponse("""
            <html>
                <head>
                    <meta http-equiv="refresh" content="2; url=/dashboard/" />
                </head>
                <body style="font-family: sans-serif; text-align: center; padding: 40px;">
                    <h2>You are not authorized to view this page.</h2>
                    <p>Redirecting you back in 2 seconds...</p>
                </body>
            </html>
        """)

    if request.method == 'POST':
        total_entries = len([key for key in request.POST if key.startswith('amount-')])
        
        for i in range(total_entries):
            try:
                ingredient_id = request.POST.get('ingredient')
                action = request.POST.get(f'action-{i}')
                amount = float(request.POST.get(f'amount-{i}'))
                unit = request.POST.get(f'unit-{i}')
                cost = float(request.POST.get(f'cost-{i}'))

                ingredient = Ingredient.objects.get(pk=ingredient_id)

                # Check unit match
                if unit != ingredient.unit:
                    continue  # skip if mismatched

                if action == 'add':
                    # Weighted average cost update
                    existing_total_cost = ingredient.quantity * ingredient.price_per_unit
                    new_total_cost = cost
                    new_total_quantity = ingredient.quantity + amount

                    if new_total_quantity > 0:
                        new_price_per_unit = (existing_total_cost + new_total_cost) / new_total_quantity
                        ingredient.price_per_unit = new_price_per_unit

                    ingredient.quantity += amount

                elif action == 'reduce':
                    ingredient.quantity = max(0, ingredient.quantity - amount)

                ingredient.save()

            except Exception as e:
                print(f"Error processing entry {i}: {e}")
                continue

        return redirect('dashboard')

    ingredients = Ingredient.objects.all()
    context = {
        'ingredients': ingredients,
        'now': timezone.now()
    }
    return render(request, 'hananApp/update_inventory.html', context)

from django.urls import reverse

def generate_report(request):
    logger.info("Entered view: generate_report")
    report_items = []

    if request.method == "POST":
        default_start = "2024-11-17"
        default_end = "2024-11-24"

        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()
        report_items = request.POST.getlist('report_items')  # Get selected report items

        if not start_date or not end_date:
            messages.error(request, "Please select both a start date and an end date.")
            return render(request, 'hananApp/generate_report.html', {
                'report_items': report_items,
                'start_date': start_date or default_start,
                'end_date': end_date or default_end,
            })

        # Redirect to the report view with the selected checkboxes and other data
        report_url = reverse('report')  
        report_url += f"?start_date={start_date}&end_date={end_date}&report_items={','.join(report_items)}"
        return redirect(report_url)

    return render(request, 'hananApp/generate_report.html')

from django.utils import timezone
from datetime import datetime

def report(request):
    logger.info("Entered view: report")
    # Get the parameters from the URL
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    report_items = request.GET.get('report_items', '').split(',')

    # Query the ingredients
    ingredients = Ingredient.objects.all()

    # Determine the status for each ingredient based on the quantity and minimum threshold
    for ingredient in ingredients:
        if ingredient.quantity == 0:
            ingredient.status = 'Out of stock'
        elif ingredient.quantity < ingredient.min_threshold:
            ingredient.status = 'Low stock'
        else:
            ingredient.status = 'In stock'

    # Get orders within the specified date range
    orders = Order.objects.filter(date__range=[start_date, end_date])

    revenue_query = OrderDetails.objects.filter(order__in=orders).annotate(
        line_total=ExpressionWrapper(
            F('quantity') * F('dish__price'),
            output_field=FloatField()
        )
    )

    revenue = revenue_query.aggregate(
        total_revenue=Sum('line_total')
    )['total_revenue'] or 0

    # Calculate Dishes Sold: Aggregate quantity sold for each dish
    dish_sales = OrderDetails.objects.filter(order__in=orders).values('dish__name').annotate(
        total_quantity=Sum('quantity')
    ).order_by('dish__name')

    # Calculate Cost: Sum of the ingredient cost for each dish ordered
    total_cost = 0
    for order in orders:
        order_details = OrderDetails.objects.filter(order=order)
        for order_detail in order_details:
            recipe_details = RecipeDetails.objects.filter(dish=order_detail.dish)
            for recipe in recipe_details:
                total_cost += recipe.quantity_used * recipe.ingredient.price_per_unit

    # Profit = Revenue - Cost
    profit = revenue - total_cost

    # ✅ Calculate Ingredient Usage for the time period
    ingredient_usage = RecipeDetails.objects.filter(
        dish__orderdetails__order__in=orders
    ).values(
        'ingredient__name',
        'ingredient__unit'
    ).annotate(
        total_used=Sum(F('quantity_used') * F('dish__orderdetails__quantity'))
    ).order_by('ingredient__name')

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'report_items': report_items,
        'ingredients': ingredients,
        'revenue': revenue,
        'cost': total_cost,
        'profit': profit,
        'dish_sales': dish_sales,
        'ingredient_usage': ingredient_usage,  # ✅ added to context
    }

    return render(request, 'hananApp/report.html', context)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Dish, RecipeDetails, Ingredient
from django.http import JsonResponse

def edit_dish(request, dish_id):
    logger.info("Entered view: edit_dish")
    
    if request.user.userprofile.role != 'admin':
        logger.warning(f"Unauthorized access attempt by user {request.user.username}")
        return HttpResponse("""
            <html>
                <head>
                    <meta http-equiv="refresh" content="2; url=/dashboard/" />
                </head>
                <body style="font-family: sans-serif; text-align: center; padding: 40px;">
                    <h2>You are not authorized to view this page.</h2>
                    <p>Redirecting you back in 2 seconds...</p>
                </body>
            </html>
        """)

    dish = get_object_or_404(Dish, id=dish_id)
    ingredients = Ingredient.objects.all()

    if request.method == 'POST':
        dish_name = request.POST.get('name')
        dish_price = request.POST.get('price')

        dish.name = dish_name
        dish.price = dish_price
        dish.save()
        logger.info(f"Updated dish '{dish.name}' with new price {dish_price}")

        existing_details = RecipeDetails.objects.filter(dish=dish)
        existing_ingredient_ids = set(existing_details.values_list('ingredient_id', flat=True))

        posted_ingredient_ids = set()
        updated_pairs = set()

        i = 1
        while True:
            ingredient_id = request.POST.get(f'ingredient_{i}')
            quantity = request.POST.get(f'quantity_{i}')
            if not ingredient_id or not quantity:
                break
            ingredient_id = int(ingredient_id)
            quantity = float(quantity)

            posted_ingredient_ids.add(ingredient_id)
            updated_pairs.add((ingredient_id, quantity))

            recipe_detail = RecipeDetails.objects.filter(dish=dish, ingredient_id=ingredient_id).first()
            if recipe_detail:
                recipe_detail.quantity_used = quantity
                recipe_detail.save()
                logger.info(f"Updated RecipeDetails: {ingredient_id} -> {quantity}")
            else:
                RecipeDetails.objects.create(dish=dish, ingredient_id=ingredient_id, quantity_used=quantity)
                logger.info(f"Created new RecipeDetails: {ingredient_id} -> {quantity}")

            i += 1

        # Delete removed ingredients
        to_delete = existing_details.exclude(ingredient_id__in=posted_ingredient_ids)
        deleted_ids = list(to_delete.values_list('ingredient_id', flat=True))
        to_delete.delete()
        if deleted_ids:
            logger.info(f"Deleted RecipeDetails for removed ingredients: {deleted_ids}")

        messages.success(request, "Dish updated successfully!")
        return redirect('dishes')

    return render(request, 'hananApp/edit_dish.html', {
        'dish': dish,
        'ingredients': ingredients
    })