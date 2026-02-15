# ai_utils.py
import pandas as pd
import pickle
import os
from django.conf import settings
from accounts.models import Order,FoodItem
from django.db.models import Count

MODEL_PATH = os.path.join(settings.BASE_DIR, 'order_predictor_model.pkl')

def state_food_stats():
    # group by city + food
    raw_data = (
        Order.objects.values("city", "food_item__name")
        .annotate(total=Count("id"))
        .order_by("city", "-total")
    )

    # pick top food per city
    city_food = {}
    for row in raw_data:
        city = row["city"] or "Unknown"
        food = row["food_item__name"]
        orders = row["total"]

        if city not in city_food:  # first (largest) row per city
            city_food[city] = {"food": food, "orders": orders}

    return city_food

def suggest_top_food_for_state(state_name: str, limit: int = 5):
    """
    Suggest the top food items for a given state (city/state stored in Order.city).
    Returns Food objects (with images, price, etc.) instead of just names.
    Falls back to global top foods if no orders exist for that state.
    """
    # First fetch IDs as a list (MySQL-safe)
    top_food_ids = list(
        Order.objects.filter(city__iexact=state_name)
        .values("food_item")  
        .annotate(count=Count("food_item"))
        .order_by("-count")
        .values_list("food_item", flat=True)[:limit]
    )

    if top_food_ids:
        return FoodItem.objects.filter(id__in=top_food_ids)

    # Fallback → global top foods
    global_top_food_ids = list(
        Order.objects.values("food_item")
        .annotate(count=Count("food_item"))
        .order_by("-count")
        .values_list("food_item", flat=True)[:limit]
    )

    return FoodItem.objects.filter(id__in=global_top_food_ids)


def get_order_data():
    orders = Order.objects.all().values("id", "user__username", "city", "item_name", "quantity", "price")
    return pd.DataFrame(list(orders))


def get_ai_predictions(limit: int = 10):
    """
    Load trained model + encoders and generate predictions for recent orders.
    Returns a list of dicts with actual vs predicted price.
    """
    if not os.path.exists(MODEL_PATH):
        return []

    with open(MODEL_PATH, "rb") as f:
        data = pickle.load(f)

    model = data['model']
    user_encoder = data['user_encoder']
    city_encoder = data['city_encoder']
    item_encoder = data['item_encoder']

    df = get_order_data().sort_values("id", ascending=False).head(limit)  # last N orders
    if df.empty:
        return []

    # Encode with same encoders
    df['user_encoded'] = df['user__username'].map(
        lambda x: user_encoder.transform([x])[0] if x in user_encoder.classes_ else 0
    )
    df['city_encoded'] = df['city'].map(
        lambda x: city_encoder.transform([x])[0] if x in city_encoder.classes_ else 0
    )
    df['item_encoded'] = df['item_name'].map(
        lambda x: item_encoder.transform([x])[0] if x in item_encoder.classes_ else 0
    )

    X = df[['user_encoded', 'city_encoded', 'item_encoded', 'quantity']]
    df['predicted_price'] = model.predict(X)

    return df[['id', 'user__username', 'city', 'item_name', 'quantity', 'price', 'predicted_price']].to_dict(orient="records")


def overall_stats():
    """
    Existing stats + AI predictions
    """
    from django.db.models import Count
    from django.contrib.auth.models import User

    # Orders by city
    state_orders = (
        Order.objects.values('city').annotate(count=Count('id')).order_by('-count')
    )
    orders_by_state_labels = [s['city'] or 'Unknown' for s in state_orders]
    orders_by_state_counts = [s['count'] for s in state_orders]
    most_ordered_state = orders_by_state_labels[0] if orders_by_state_labels else 'N/A'

    # Top users
    user_orders = (
        Order.objects.values('user__username')
        .annotate(count=Count('id')).order_by('-count')[:5]
    )
    top_users = [(u['user__username'], u['count']) for u in user_orders]

    total_orders = Order.objects.count()
    total_users = User.objects.filter(order__isnull=False).distinct().count()

    # Food stats per city
    from .ai_utils import state_food_stats
    city_food = state_food_stats()

    # AI predictions
    predictions = get_ai_predictions(limit=10)

    return {
        "orders_by_state_labels": orders_by_state_labels,
        "orders_by_state_counts": orders_by_state_counts,
        "most_ordered_state": most_ordered_state,
        "top_users": top_users,
        "total_orders": total_orders,
        "total_users": total_users,
        "city_food": city_food,
        "predictions": predictions,
    }
