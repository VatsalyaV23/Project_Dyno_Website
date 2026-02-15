import os
import django
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import LabelEncoder
import pickle

# -----------------------------
# Setup Django Environment
# -----------------------------
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Dyno.settings')
django.setup()

from accounts.models import Order

MODEL_FILE = "order_predictor_model.pkl"

# -----------------------------
# Load Order Data into DataFrame
# -----------------------------
def get_order_df():
    """
    Fetch all order records from the database and convert them into a Pandas DataFrame.
    Cleans null values to ensure smooth model training.
    """
    orders = Order.objects.all().values('user__username', 'city', 'item_name', 'quantity', 'price')
    df = pd.DataFrame(orders)

    # Drop rows with missing values
    df.dropna(subset=["user__username", "city", "item_name", "quantity", "price"], inplace=True)
    return df


# -----------------------------
# Train Model and Save with Encoders
# -----------------------------
def train_and_save_model():
    """
    Train a Linear Regression model using user, city, item, and quantity to predict price.
    Encodes categorical variables before training.
    Also evaluates accuracy and saves the trained model.
    """
    df = get_order_df()
    if df.empty:
        print("No data to train.")
        return None

    # Encode categorical features
    user_encoder = LabelEncoder()
    city_encoder = LabelEncoder()
    item_encoder = LabelEncoder()

    df['user_encoded'] = user_encoder.fit_transform(df['user__username'])
    df['city_encoded'] = city_encoder.fit_transform(df['city'])
    df['item_encoded'] = item_encoder.fit_transform(df['item_name'])

    # Features (X) and Target (y)
    X = df[['user_encoded', 'city_encoded', 'item_encoded', 'quantity']]
    y = df['price']

    # Train Linear Regression Model
    model = LinearRegression()
    model.fit(X, y)

    # -----------------------------
    # Evaluate Model Accuracy
    # -----------------------------
    y_pred = model.predict(X)

    print(f"✅ Model trained successfully!")

    # -----------------------------
    # Visualization - Actual vs Predicted
    # -----------------------------
    plt.figure(figsize=(8, 5))
    plt.scatter(y, y_pred, alpha=0.7, edgecolor='k')
    plt.plot([y.min(), y.max()], [y.min(), y.max()], 'r--')  # reference line
    plt.xlabel("Actual Price")
    plt.ylabel("Predicted Price")
    plt.title("Actual vs Predicted Price")
    plt.show()

    # Save model and encoders
    with open(MODEL_FILE, 'wb') as f:
        pickle.dump({
            'model': model,
            'user_encoder': user_encoder,
            'city_encoder': city_encoder,
            'item_encoder': item_encoder
        }, f)


# -----------------------------
# Prediction Function
# -----------------------------
def predict_price(user, city, item, quantity):
    """
    Predicts the price for a given user, city, item, and quantity
    using the trained Linear Regression model.
    Handles unseen labels gracefully by assigning default values.
    """
    # Ensure latest model
    train_and_save_model()

    if not os.path.exists(MODEL_FILE):
        print("No model available.")
        return None

    with open(MODEL_FILE, 'rb') as f:
        data = pickle.load(f)

    model = data['model']
    user_encoder = data['user_encoder']
    city_encoder = data['city_encoder']
    item_encoder = data['item_encoder']

    # Handle unseen labels
    try:
        user_val = user_encoder.transform([user])[0]
    except:
        user_val = 0
    try:
        city_val = city_encoder.transform([city])[0]
    except:
        city_val = 0
    try:
        item_val = item_encoder.transform([item])[0]
    except:
        item_val = 0

    # Make prediction
    X_pred = [[user_val, city_val, item_val, quantity]]
    pred_price = model.predict(X_pred)[0]
    return pred_price

# -----------------------------
# Run Training when Script is Executed
# -----------------------------
if __name__ == "__main__":
    print("🚀 Starting AI Training...")
    train_and_save_model()

