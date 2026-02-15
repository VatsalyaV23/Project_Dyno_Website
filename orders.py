import os
import django
import random
from django.utils import timezone

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Dyno.settings")  # Replace 'Dyno' with your project name
django.setup()

from django.contrib.auth.models import User
from accounts.models import FoodItem, Order, Profile  # Make sure Profile is imported

users = User.objects.all()
foods = list(FoodItem.objects.all())

if not foods:
    print("⚠️ No food items found. Add food items first.")
else:
    for user in users:
        # ✅ Skip staff users (optional)
        if user.is_staff:
            continue

        try:
            profile = user.profile  # 🔄 Fetch user’s profile
            gender = profile.gender
            city = profile.city
            
        except Profile.DoesNotExist:
            print(f"⚠️ Profile missing for {user.username}")
            continue

        for _ in range(random.randint(4, 5)):
            food = random.choice(foods)
            quantity = random.randint(1, 3)
            price = food.price * quantity

            Order.objects.create(
                user=user,
                food_item=food,
                item_name=food.name,
                price=price,
                quantity=quantity,
                description=getattr(food, "description", "No description"),
                image=getattr(food, "image", None),
                timestamp=timezone.now(),
                placed_at=timezone.now(),
                estimated_delivery_minutes=random.randint(20, 60),
                payment_method=random.choice(["COD", "Online"]),
                gender=gender,
                city=city,
                name=profile.name,  # ✅ Always save name
                username=user.username,  # ✅ Always save username
            )
    print("✅ Successfully created orders.")


