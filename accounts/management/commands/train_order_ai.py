import os
import pandas as pd
from django.core.management.base import BaseCommand
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import LabelEncoder
import pickle
from accounts.models import Order

class Command(BaseCommand):
    help = 'Trains and saves the order prediction AI model.'

    def handle(self, *args, **kwargs):
        orders = Order.objects.all().values('username', 'city', 'item_name', 'quantity', 'price')
        df = pd.DataFrame(orders)
        df.dropna(subset=["username", "city", "item_name", "quantity", "price"], inplace=True)

        if df.empty:
            self.stdout.write("No data to train the model.")
            return

        user_encoder = LabelEncoder()
        city_encoder = LabelEncoder()
        item_encoder = LabelEncoder()

        df['user_encoded'] = user_encoder.fit_transform(df['username'])
        df['city_encoded'] = city_encoder.fit_transform(df['city'])
        df['item_encoded'] = item_encoder.fit_transform(df['item_name'])

        X = df[['user_encoded', 'city_encoded', 'item_encoded', 'quantity']]
        y = df['price']

        model = LinearRegression()
        model.fit(X, y)

        # Save model and encoders
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        model_path = os.path.join(project_root, 'order_predictor_model.pkl')
        with open(model_path, 'wb') as f:
            pickle.dump({
                'model': model,
                'user_encoder': user_encoder,
                'city_encoder': city_encoder,
                'item_encoder': item_encoder
            }, f)
        self.stdout.write(f"✅ Model trained and saved to {model_path}.")