"""
Django management command to train the predictive maintenance model
using historical sensor data from the database.

Usage: python manage.py train_predictive_model
"""

from django.core.management.base import BaseCommand
from core.models import SensorReading, AutomationLog
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import pickle
import os
from django.conf import settings
from datetime import timedelta
from django.utils import timezone


class Command(BaseCommand):
    help = 'Train predictive maintenance models using historical sensor data'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🤖 PREDICTIVE MAINTENANCE MODEL TRAINING'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # Step 1: Fetch historical data
        self.stdout.write('\n📊 Fetching historical sensor data...')
        readings = SensorReading.objects.all().order_by('timestamp')
        
        if readings.count() < 100:
            self.stdout.write(self.style.WARNING(
                f'⚠️  Only {readings.count()} readings available. Need at least 100 for training.'
            ))
            self.stdout.write(self.style.WARNING(
                '   Run the simulator for a few hours to collect more data.'
            ))
            return
        
        self.stdout.write(self.style.SUCCESS(f'   ✅ Found {readings.count()} sensor readings'))
        
        # Step 2: Prepare training data
        self.stdout.write('\n🔧 Preparing training data...')
        data = self.prepare_training_data(readings)
        
        if len(data) < 50:
            self.stdout.write(self.style.ERROR('   ❌ Not enough data for training'))
            return
        
        df = pd.DataFrame(data)
        self.stdout.write(self.style.SUCCESS(f'   ✅ Prepared {len(df)} training samples'))
        
        # Step 3: Train models
        self.stdout.write('\n🎯 Training classification models...')
        models = self.train_models(df)
        
        # Step 4: Save models
        self.stdout.write('\n💾 Saving trained models...')
        model_path = os.path.join(settings.BASE_DIR, 'predictive_maintenance_models.pkl')
        
        with open(model_path, 'wb') as f:
            pickle.dump(models, f)
        
        self.stdout.write(self.style.SUCCESS(f'   ✅ Models saved to: {model_path}'))
        
        # Step 5: Summary
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('✅ TRAINING COMPLETE'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('\nThe system can now predict and prevent:')
        self.stdout.write('  🌊 Humidity drops (activate humidifier proactively)')
        self.stdout.write('  💨 CO2 spikes (activate ventilation proactively)')
        self.stdout.write('  🔥 Temperature drops (activate heater proactively)')
        self.stdout.write('\n' + '=' * 70 + '\n')

    def prepare_training_data(self, readings):
        """
        Analyze historical sensor data and create training samples.
        Labels are based on whether conditions went out of range.
        """
        OPTIMAL_TEMP = 23.0
        OPTIMAL_HUMIDITY = 85.0
        OPTIMAL_CO2 = 900
        
        data = []
        readings_list = list(readings)
        
        for i in range(len(readings_list) - 5):  # Look 5 readings ahead
            current = readings_list[i]
            future_readings = readings_list[i+1:i+6]
            
            # Calculate if conditions drop in the next hour
            future_humidity = [float(r.humidity) for r in future_readings]
            future_co2 = [r.co2_ppm for r in future_readings]
            future_temp = [float(r.temperature) for r in future_readings]
            
            # Labels: Will we need action in the next hour?
            activate_humidifier = 1 if min(future_humidity) < (OPTIMAL_HUMIDITY - 5) else 0
            activate_ventilation = 1 if max(future_co2) > (OPTIMAL_CO2 + 100) else 0
            activate_heater = 1 if min(future_temp) < (OPTIMAL_TEMP - 2) else 0
            
            data.append({
                'hour_of_day': current.timestamp.hour,
                'temperature': float(current.temperature),
                'humidity': float(current.humidity),
                'co2': current.co2_ppm,
                'activate_humidifier': activate_humidifier,
                'activate_ventilation': activate_ventilation,
                'activate_heater': activate_heater
            })
        
        return data

    def train_models(self, df):
        """Train three classification models for predictive actions"""
        features = ['hour_of_day', 'temperature', 'humidity', 'co2']
        X = df[features]
        
        # Split data
        X_train, X_test = train_test_split(X, test_size=0.2, random_state=42)
        
        models = {}
        
        # Train Humidifier Model
        self.stdout.write('   🌊 Training humidifier model...')
        y_hum = df['activate_humidifier']
        y_hum_train, y_hum_test = train_test_split(y_hum, test_size=0.2, random_state=42)
        
        model_hum = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
        model_hum.fit(X_train, y_hum_train)
        
        accuracy_hum = model_hum.score(X_test, y_hum_test)
        self.stdout.write(self.style.SUCCESS(f'      ✅ Accuracy: {accuracy_hum*100:.1f}%'))
        
        # Train Ventilation Model
        self.stdout.write('   💨 Training ventilation model...')
        y_vent = df['activate_ventilation']
        y_vent_train, y_vent_test = train_test_split(y_vent, test_size=0.2, random_state=42)
        
        model_vent = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
        model_vent.fit(X_train, y_vent_train)
        
        accuracy_vent = model_vent.score(X_test, y_vent_test)
        self.stdout.write(self.style.SUCCESS(f'      ✅ Accuracy: {accuracy_vent*100:.1f}%'))
        
        # Train Heater Model
        self.stdout.write('   🔥 Training heater model...')
        y_heat = df['activate_heater']
        y_heat_train, y_heat_test = train_test_split(y_heat, test_size=0.2, random_state=42)
        
        model_heat = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
        model_heat.fit(X_train, y_heat_train)
        
        accuracy_heat = model_heat.score(X_test, y_heat_test)
        self.stdout.write(self.style.SUCCESS(f'      ✅ Accuracy: {accuracy_heat*100:.1f}%'))
        
        return {
            'humidifier': model_hum,
            'ventilation': model_vent,
            'heater': model_heat,
            'features': features,
            'optimal_values': {
                'temperature': 23.0,
                'humidity': 85.0,
                'co2': 900
            }
        }
