import time
import random
from django.core.management.base import BaseCommand
from core.models import SensorReading, Notification, EnvironmentSettings 

class Command(BaseCommand):
    help = 'Runs the IoT sensor simulator'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting sensor simulator...'))
        
        # --- SYSTEM NOTIFICATION ---
        # Create a "System" alert on startup
        Notification.objects.create(
            title="System Started",
            description="Sensor simulator is now online and generating data.",
            category="system",
            level="info"
        )
        self.stdout.write(self.style.SUCCESS('Created "System Started" notification.'))

        temp_norm = 23.0
        hum_norm = 82.0
        co2_norm = 900

        while True:
            try:
                # 1. Generate a new random sensor reading
                new_temp = temp_norm + random.uniform(-1.5, 1.5)
                new_hum = hum_norm + random.uniform(-3.0, 3.0)
                new_co2 = co2_norm + random.randint(-50, 50)

                # 2. Create and save the new reading
                reading = SensorReading.objects.create(
                    temperature=round(new_temp, 1),
                    humidity=round(new_hum, 1),
                    co2_ppm=new_co2
                )
                
                self.stdout.write(
                    f"Saved new reading: {reading.temperature}°C, "
                    f"{reading.humidity}%, {reading.co2_ppm}ppm"
                )
                
                # --- UPDATED: EQUIPMENT NOTIFICATION ---
                # 3. Simulate equipment failure chance based on settings
                
                # Get the current settings
                settings = EnvironmentSettings.load()
                
                # Base chance of 1%
                failure_chance = 1 
                
                # If fan is running at > 90%, add 5% chance
                if settings.fan_on and settings.fan_value > 90:
                    failure_chance += 5
                
                # If humidifier is at > 95%, add 5% chance
                if settings.humidifier_on and settings.humidifier_value > 95:
                    failure_chance += 5
                
                # Check if we trigger a failure
                if random.randint(1, 100) <= failure_chance:
                    if not Notification.objects.filter(title="Equipment Stress Warning", is_read=False).exists():
                        Notification.objects.create(
                            title="Equipment Stress Warning",
                            description="High load detected on environment controls. Check equipment for maintenance.",
                            category="equipment",
                            level="warning"
                        )
                        self.stdout.write(self.style.WARNING(f'*** Simulated Equipment Stress! (Chance: {failure_chance}%) Created "Equipment" notification. ***'))
                # --- END UPDATED ---

                # 4. Wait for 10 seconds
                time.sleep(10)

            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING('Stopping simulator.'))
                break
            except Exception as e:
                # Add a general exception handler so the simulator doesn't crash
                self.stdout.write(self.style.ERROR(f'Simulator error: {e}'))
                time.sleep(10) # Wait 10 seconds before retrying