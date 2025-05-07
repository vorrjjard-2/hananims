import heapq
from django.db.models import F
from .models import Ingredient

def priority_queue(ingredients):
    priority_queue = []

    # Push each ingredient into the heap
    for ingredient in ingredients:
        heapq.heappush(priority_queue, (-ingredient.shortage, ingredient.id))

    # Create an empty list to store the sorted ingredients
    sorted_ingredients = []

    # Pop items one by one from the heap and fetch them from the database
    while priority_queue:
        _, ingredient_id = heapq.heappop(priority_queue)
        sorted_ingredients.append(ingredients.get(id=ingredient_id))

    # Print the first item (ingredient with the highest shortage)
    if sorted_ingredients:
        print(sorted_ingredients[0])
    return sorted_ingredients


def merge_sort(arr, key):
    # Base case: if the list is a single element, it's already sorted
    if len(arr) <= 1:
        return arr
    
    # Divide the list into two halves
    mid = len(arr) // 2
    left_half = merge_sort(arr[:mid], key)
    right_half = merge_sort(arr[mid:], key)
    
    # Merge the sorted halves
    return merge(left_half, right_half, key)

def merge(left, right, key):
    sorted_list = []
    while left and right:
        # Reverse the comparison for ascending order of priority (1 is highest priority)
        if getattr(left[0], key) < getattr(right[0], key):  # Lower value is higher priority
            sorted_list.append(left.pop(0))
        else:
            sorted_list.append(right.pop(0))
    
    # If there are any elements left in either list, add them
    sorted_list.extend(left)
    sorted_list.extend(right)
    
    return sorted_list
# Function to sort dishes using bubble sort
def insertion_sort(dishes, key):
    n = len(dishes)

    for i in range(1, n):  # Start from the second element
        key_item = dishes[i]
        j = i - 1

        # Move elements of dishes[0..i-1] that are greater than key_item to one position ahead
        while j >= 0 and dishes[j][key] < key_item[key]:  # Descending order
            dishes[j + 1] = dishes[j]
            j -= 1

        dishes[j + 1] = key_item

    return dishes