# views.py
import os
import json
import random
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db.models import Count
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import FoodItem, CartItem, Order, Profile
from .ai_utils import overall_stats, suggest_top_food_for_state


# Simulated cart storage (to be replaced with DB model in production)
user_cart = {}


def register_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        gender = request.POST.get('gender')
        username = request.POST.get('username')
        email = request.POST.get('email')
        city = request.POST.get('city')
        dob = request.POST.get('dob')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('register')
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return redirect('register')

        is_staff_user = email.endswith('@dyno.com')
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            first_name=first_name,
        )
        user.is_staff = is_staff_user
        user.save()

        try:
            parsed_dob = datetime.strptime(dob, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Invalid DOB format. Use YYYY-MM-DD.")
            user.delete()
            return redirect('register')

        # Now update profile (created by signal)
        profile = user.profile
        profile.username = username
        profile.gender = gender
        profile.city = city
        profile.dob = parsed_dob
        profile.name = first_name
        profile.is_staff_member = is_staff_user
        profile.save()

        messages.success(request, "Account created successfully!")
        return redirect('login')

    return render(request, 'accounts/register.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not username or not password:
            messages.error(request, "Please enter both username and password.")
            return redirect('login')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Redirect to next page if provided, otherwise to dashboard
            next_url = request.GET.get('next')
            if user.is_staff:
                return redirect('staff_dashboard')
            return redirect(next_url or 'dashboard')
        else:
            messages.error(request, "Invalid credentials.")
            return redirect('login')

    return render(request, 'accounts/login.html')



def logout_view(request):
    logout(request)
    return redirect('login')


def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, 'accounts/dashboard.html')

# --- FILTERED FOOD LIST FOR HOME ---
def get_filtered_food_items(request):
    food_items = FoodItem.objects.all()
    query = request.GET.get('q', '')
    cuisine = request.GET.get('cuisine', '')
    veg = request.GET.get('veg')
    nonveg = request.GET.get('nonveg')
    sort = request.GET.get('sort')

    # Search by name
    if query:
        food_items = food_items.filter(name__icontains=query)
    # Cuisine filter (assume cuisine in description)
    if cuisine and cuisine != 'All':
        food_items = food_items.filter(description__icontains=cuisine)
    # Veg filter (assume 'veg'/'nonveg' in description)
    if veg and not nonveg:
        food_items = food_items.filter(description__icontains='veg')
    elif nonveg and not veg:
        food_items = food_items.filter(description__icontains='nonveg')
    # Sorting
    if sort == 'price_low':
        food_items = food_items.order_by('price')
    elif sort == 'price_high':
        food_items = food_items.order_by('-price')
    elif sort == 'rating':
        # For demo, skip actual rating sorting if not present in model
        pass
    return food_items


def home(request):
    categories = "All,Indian,Chinese,Italian,Continental,Thai,South Indian,North Indian".split(',')
    food_items = get_filtered_food_items(request)
    query = request.GET.get('q', '')
    cuisine = request.GET.get('cuisine', '')
    veg = request.GET.get('veg')
    nonveg = request.GET.get('nonveg')
    sort = request.GET.get('sort')

    suggested_foods = None
    if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.city:
        city = request.user.profile.city
        suggested_foods = suggest_top_food_for_state(city)

    context = {
        'food_items': food_items,
        'query': query,
        'categories': categories,
        'cuisine': cuisine,
        'veg': veg,
        'nonveg': nonveg,
        'sort': sort,
        'suggested_foods': suggested_foods,
    }

    return render(request, "accounts/home.html", context)

    
# --- CART LOGIC ---
@login_required
def add_to_cart(request, food_id):
    food = get_object_or_404(FoodItem, id=food_id)
    cart = request.session.get('cart', {})
    food_id = str(food_id)
    if food_id in cart:
        cart[food_id]['quantity'] += 1
    else:
        cart[food_id] = {
            'name': food.name,
            'price': float(food.price),
            'image': food.image.url if food.image else '',
            'quantity': 1,
        }
    request.session['cart'] = cart
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    messages.success(request, f"{food.name} added to cart.")
    return redirect('home')

@login_required
@csrf_exempt
def add_to_cart_ajax(request, food_id):
    return add_to_cart(request, food_id)

@login_required
def cart_view(request):
    cart = request.session.get('cart', {})
    cart_items = []
    total_price = 0

    for food_id_str, item_data in cart.items():
        try:
            food_id = int(food_id_str)
            food = FoodItem.objects.get(pk=food_id)
        except (FoodItem.DoesNotExist, ValueError):
            continue

        # Handle both simple quantity or dict with quantity
        quantity = item_data['quantity'] if isinstance(item_data, dict) else item_data

        subtotal = float(food.price) * quantity  # convert Decimal to float for safety

        cart_items.append({
            'id': food.id,
            'name': food.name,
            'image': food.image.url,
            'price': float(food.price),
            'quantity': quantity,
            'total': subtotal
        })
        total_price += subtotal

    return render(request, 'accounts/cart.html', {
        'cart_items': cart_items,
        'total_price': total_price
    })


@require_POST
@login_required
def update_quantity(request):
    data = json.loads(request.body)
    food_id = data.get('item_name')
    action = data.get('action')
    cart = request.session.get('cart', {})
    if food_id in cart:
        if action == 'increase':
            cart[food_id]['quantity'] += 1
        elif action == 'decrease' and cart[food_id]['quantity'] > 1:
            cart[food_id]['quantity'] -= 1
    request.session['cart'] = cart
    quantity = cart[food_id]['quantity']
    subtotal = cart[food_id]['price'] * quantity
    total_price = sum(item['price'] * item['quantity'] for item in cart.values())
    return JsonResponse({'success': True, 'quantity': quantity, 'subtotal': subtotal, 'total_price': total_price})


@require_POST
@login_required
def remove_from_cart(request):
    food_id = request.POST.get('item_name')
    cart = request.session.get('cart', {})
    if food_id in cart:
        del cart[food_id]
        request.session['cart'] = cart
    return redirect('cart')


def about_view(request):
    return render(request, 'accounts/about.html')

def contact_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        query = request.POST.get('query')
        # Optional: store in DB or send email
        print(f"Query from {name} ({email}): {query}")
        messages.success(request, "Thanks! We’ve received your message.")
        return redirect('contact')  # redirect to the same page after post

    return render(request, 'accounts/contact.html')

@login_required
def orders_view(request):
    orders = Order.objects.filter(user=request.user).order_by('-timestamp')
    
    for order in orders:
        # Add delivery status dynamically
        time_diff = timezone.now() - order.timestamp
        order.status = 'Delivering' if time_diff < timedelta(minutes=order.estimated_delivery_minutes) else 'Delivered'
        order.remaining_time = max(0, (order.estimated_delivery_minutes * 60 - time_diff.total_seconds()) // 60)

    return render(request, 'accounts/orders.html', {'orders': orders})

@login_required
def order_again_view(request, order_id):
    from .models import Order
    original_order = Order.objects.get(id=order_id, user=request.user)
    
    # Create a duplicate order
    Order.objects.create(
        user=request.user,
        item_name=original_order.item_name,
        description=original_order.description,
        image=original_order.image,
        price=original_order.price,
        
    )
    return redirect('orders')

@login_required
def staff_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    food_items = FoodItem.objects.all().order_by('-created_at')
    return render(request, 'accounts/staff_dashboard.html',{'food_items':food_items})


@login_required
def add_food(request):
    if not request.user.is_staff:
        return redirect('home')

    if request.method == 'POST':
        name = request.POST.get('name')
        price_input = request.POST.get('price')
        image = request.FILES.get('image')
        description = request.POST.get('description')

        try:
            price = Decimal(price_input)
        except (InvalidOperation, TypeError):
            return render(request, 'accounts/add_food.html', {
                'error': 'Please enter a valid price.',
                'name': name,
                'description': description
            })

        FoodItem.objects.create(
            name=name,
            price=price,
            image=image,
            description=description,
            added_by=request.user
        )

        return redirect('staff_dashboard')

    return render(request, 'accounts/add_food.html')

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Set is_staff_member=True if email ends with '@dyno.com'
        is_staff = instance.email.endswith('@dyno.com')
        Profile.objects.create(user=instance, is_staff_member=is_staff)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        # In case the profile was somehow not created yet
        is_staff = instance.email.endswith('@dyno.com')
        Profile.objects.create(user=instance, is_staff_member=is_staff)
        
@login_required
def delete_food(request, food_id):
    if not request.user.profile.is_staff_member:
        return redirect('home')

    food = get_object_or_404(FoodItem, id=food_id)

    if request.method == 'POST':
        food.delete()
        return redirect('staff_dashboard')
   
@login_required
def order_now(request, food_id):
    food = get_object_or_404(FoodItem, id=food_id)
    profile = getattr(request.user, 'profile', None)
    order_placed = False
    tracking = None
    if request.method == 'POST':
        Order.objects.create(
            user=request.user,
            food_item=food,
            quantity=1,
            address="DYNO Default Address",
            delivery_time=(timezone.now() + timedelta(minutes=30)).time(),
            payment_method="Cash on Delivery",
            price=food.price,
            item_name=food.name,
            description=food.description,
            image=food.image if food.image else None,
            name=profile.name if profile and profile.name else request.user.first_name,
            gender=profile.gender if profile and profile.gender else '',
            city=profile.city if profile and profile.city else '',
            username=request.user.username,  # ✅ Always take from request.user
        )
        order_placed = True
        tracking = {
            'status': 'Delivering',
            'eta': 30
        }
    else:
        order = Order.objects.filter(user=request.user, food_item=food).order_by('-timestamp').first()
        if order:
            order_placed = True
            time_diff = timezone.now() - order.timestamp
            remaining = max(0, 30 - int(time_diff.total_seconds() // 60))
            tracking = {
                'status': 'Delivering' if remaining > 0 else 'Delivered',
                'eta': remaining
            }
    return render(request, 'accounts/order_now.html', {'food': food, 'order_placed': order_placed, 'tracking': tracking})


@login_required
def place_order(request):
    if request.method == 'POST':
        food_id = request.POST.get('food_id')
        address = request.POST.get('address', 'DYNO Default Address')
        quantity = int(request.POST.get('quantity', 1))

        food = get_object_or_404(FoodItem, id=food_id)
        profile = getattr(request.user, 'profile', None)

        Order.objects.create(
            user=request.user,
            food_item=food,
            quantity=quantity,
            address=address,
            delivery_time=(timezone.now() + timedelta(minutes=30)).time(),
            payment_method="Cash on Delivery",
            price=food.price,
            item_name=food.name,
            description=food.description,
            image=food.image if food.image else None,
            name=profile.name if profile and profile.name else request.user.first_name,
            gender=profile.gender if profile and profile.gender else '',
            city=profile.city if profile and profile.city else '',
            username=request.user.username,  # ✅ Always take from request.user
        )
        return redirect('order_success')
    return redirect('home')


@login_required
def order_success(request):
    return render(request, 'accounts/order_success.html')

from datetime import datetime, timedelta
delivery_time = (datetime.now() + timedelta(hours=1)).time()

@login_required
def order_all(request):
    cart = request.session.get('cart', {})
    if not cart:
        return redirect('cart')
    profile = getattr(request.user, 'profile', None)
    for food_id_str, item in cart.items():
        try:
            food_id = int(food_id_str)
            food = FoodItem.objects.get(pk=food_id)
            Order.objects.create(
                user=request.user,
                food_item=food,
                quantity=item['quantity'],
                address="DYNO Default Address",
                delivery_time=(timezone.now() + timedelta(minutes=30)).time(),
                payment_method="Cash on Delivery",
                price=food.price,
                item_name=food.name,
                description=food.description,
                image=food.image if food.image else None,
                name=profile.name if profile and profile.name else request.user.first_name,
                gender=profile.gender if profile and profile.gender else '',
                city=profile.city if profile and profile.city else '',
                username=request.user.username,  # ✅ Always take from request.user
            )
        except (FoodItem.DoesNotExist, ValueError, AttributeError):
            continue

    request.session['cart'] = {}
    request.session.modified = True

    return redirect('orders')


@login_required
def orders_view(request):
    orders = Order.objects.filter(user=request.user).order_by('-timestamp')
    delivery_duration = timedelta(minutes=30)
    for order in orders:
        time_diff = timezone.now() - order.timestamp
        if time_diff < delivery_duration:
            order.status = "Delivering"
            order.remaining_time = int((delivery_duration - time_diff).total_seconds() // 60)
        else:
            order.status = "Delivered"
            order.remaining_time = 0
    return render(request, 'accounts/orders.html', {'orders': orders})

@login_required
def order_again_view(request, order_id):
    original_order = get_object_or_404(Order, id=order_id, user=request.user)
    Order.objects.create(
        user=request.user,
        food_item=original_order.food_item,
        quantity=original_order.quantity,
        address=original_order.address,
        delivery_time=(timezone.now() + timedelta(minutes=30)).time(),
        payment_method=original_order.payment_method,
        price=original_order.food_item.price
    )
    return redirect('orders')

def order_list_view(request):
    orders = Order.objects.filter(user=request.user).order_by('-timestamp')
    delivery_duration = timedelta(minutes=30)  # you can set as needed

    for order in orders:
        time_diff = timezone.now() - order.timestamp
        if time_diff < delivery_duration:
            order.status = "Delivering..."
            order.remaining_time = int((delivery_duration - time_diff).total_seconds() // 60)
        else:
            order.status = "Delivered"
            order.remaining_time = 0

    return render(request, 'accounts/orders.html', {'orders': orders})

def food_detail(request, food_id):
    food = get_object_or_404(FoodItem, id=food_id)
    return render(request, 'accounts/food_detail.html', {'food': food})

from .ai_utils import overall_stats, get_ai_predictions  # ✅ import prediction function

@login_required
def staff_stats(request):
    # Use AI/ML-powered statistics
    stats = overall_stats()

    # Get AI predictions (overall last 10)
    ai_predictions = get_ai_predictions()

    # Check if staff entered a state
    state_query = request.GET.get("state")  # from ?state=Delhi
    suggestion = None
    state_predictions = []

    if state_query:
        suggestion = suggest_top_food_for_state(state_query)

    context = {
        "orders_by_state_labels": stats["orders_by_state_labels"],
        "orders_by_state_counts": stats["orders_by_state_counts"],
        "most_ordered_state": stats["most_ordered_state"],
        "top_users": stats["top_users"],
        "total_orders": stats["total_orders"],
        "total_users": stats["total_users"],
        "city_food": stats["city_food"],          # city-wise top food analytics
        "ai_predictions": ai_predictions,          # overall AI predictions
        "state_query": state_query,                # keep entered state in the form
        "suggestion": suggestion,                  # AI top food suggestion for state
        "state_predictions": state_predictions,    # state-specific predictions
    }
    return render(request, "accounts/staff_stats.html", context)

@login_required
def chatbot_view(request):
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        user_message = data.get("message", "").lower()

        bot_reply = "🤖 Sorry, I can only help with food items, prices, and delivery info."

        # Food suggestions (random)
        suggestions = [
            "🍕 How about trying our Farmhouse Pizza today?",
            "🍔 A Cheese Burger with crispy fries would be amazing!",
            "🍝 Pasta lovers say our White Sauce Pasta is unbeatable!",
            "🥪 You could go for a Chicken Sandwich with a cold drink.",
            "🥗 Feeling healthy? Try our Fresh Veggie Salad."
        ]

        # Food menu queries
        if "pizza" in user_message:
            bot_reply = "🍕 We have Margherita, Farmhouse, and Peppy Paneer pizzas. Starting at ₹199!"
        elif "burger" in user_message:
            bot_reply = "🍔 Our bestsellers are Cheese Burger (₹99) and Chicken Burger (₹149)."
        elif "pasta" in user_message:
            bot_reply = "🍝 Try our White Sauce Pasta (₹179) or Red Sauce Pasta (₹159)."

        # Suggestions / recommendations
        elif "suggest" in user_message or "recommend" in user_message or "what should i eat" in user_message:
            bot_reply = random.choice(suggestions)

        # General queries
        elif "delivery" in user_message:
            bot_reply = "🚚 Delivery usually takes 30–40 minutes depending on your location."
        elif "price" in user_message or "cost" in user_message or "rate" in user_message:
            bot_reply = "💰 Prices start at ₹99 for burgers, ₹159 for pasta, and ₹199 for pizzas."
        elif "menu" in user_message or "order today" in user_message:
            bot_reply = "📖 Today’s menu: Burgers, Pizzas, Pasta, Fries, and Drinks. What would you like?"
        elif "offer" in user_message or "discount" in user_message:
            bot_reply = "🎉 Today’s offer: Get 20% off on all Pizzas! Use code PIZZA20."
        elif "timing" in user_message or "open" in user_message:
            bot_reply = "🕒 We are open daily from 10 AM to 11 PM."
        elif "payment" in user_message or "pay" in user_message:
            bot_reply = "💳 We accept COD, UPI, and all major cards."

        # Small talk / friendly replies
        elif "hello" in user_message or "hi" in user_message:
            bot_reply = "👋 Hello! I’m DYNO, your food assistant. How can I help you today?"
        elif "how are you" in user_message:
            bot_reply = "😃 I’m great, thanks for asking! Ready to take your food order. How about you?"
        elif "thank" in user_message:
            bot_reply = "🙏 You’re welcome! Happy to help."
        elif "bye" in user_message or "goodnight" in user_message:
            bot_reply = "👋 Goodbye! Have a tasty day ahead!"

        # Fallback
        elif "help" in user_message:
            bot_reply = "🤝 You can ask me about menu, prices, offers, delivery, or payment options."

        return JsonResponse({"reply": bot_reply})

    return JsonResponse({"reply": "Invalid request."})