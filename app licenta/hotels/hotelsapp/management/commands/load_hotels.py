import csv
import json
import psycopg2
import ast
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Load hotel data from offerings.csv into the database'

    def handle(self, *args, **kwargs):
        self.load_hotels()

    def sanitize_json(self, json_str):
        """
        Sanitize JSON string by converting it using ast.literal_eval
        and then dumping it back to a JSON string.
        """
        try:
            json_obj = ast.literal_eval(json_str)
            return json.dumps(json_obj)
        except (ValueError, SyntaxError) as e:
            self.stdout.write(self.style.ERROR(f"Error sanitizing JSON string: {json_str} - {e}"))
            return '{}'

    def load_hotels(self):
        conn = psycopg2.connect(
            dbname=settings.DATABASES['default']['NAME'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT']
        )
        conn.autocommit = True
        cursor = conn.cursor()

        with open(r'D:\app licenta\offerings.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                try:
                    # Sanitize the JSON fields
                    address_str = self.sanitize_json(row['address'])
                    details_str = self.sanitize_json(row['details']) if row['details'] else '{}'
                    
                    # Parse JSON fields
                    address = json.loads(address_str)
                    details = json.loads(details_str)
                except json.JSONDecodeError as e:
                    self.stdout.write(self.style.ERROR(f"Error parsing JSON in row {row}: {e}"))
                    continue

                # Provide default values if fields are empty
                phone = row['phone'] if row['phone'] else ""
                hotel_class = float(row['hotel_class']) if row['hotel_class'] else 0.0

                cursor.execute(
                    """
                    INSERT INTO hotelsapp_hotel (id, name, address, region_id, url, phone, hotel_class, details, type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (row['id'], row['name'], json.dumps(address), row['region_id'], row['url'], phone, hotel_class, json.dumps(details), row['type'])
                )
                self.stdout.write(self.style.SUCCESS(f"Successfully inserted Hotel: {row['name']} (ID: {row['id']})"))

        cursor.close()
        conn.close()
