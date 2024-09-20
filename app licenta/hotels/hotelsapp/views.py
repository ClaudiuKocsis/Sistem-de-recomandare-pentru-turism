from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordChangeForm
from .models import Hotel, Review, HotelOverallRating
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
import requests
from django.conf import settings
from django.db import connection

def home(request):
    return render(request, 'hotelsapp/home.html')

def get_recommended_hotels(user):
    with connection.cursor() as cursor:
        # Step 1: Find all hotels reviewed by the current user with at least 3.5 rating
        cursor.execute("""
            SELECT DISTINCT h.id
            FROM hotelsapp_hotel h
            JOIN hotelsapp_review r ON h.id = r.hotel_id
            WHERE r.author->>'username' = %s
              AND CAST(r.ratings->>'overall' AS NUMERIC) >= 3.5
        """, [user.username])
        reviewed_hotels = cursor.fetchall()

    if reviewed_hotels:
        reviewed_hotel_ids = [row[0] for row in reviewed_hotels]

        with connection.cursor() as cursor:
            # Step 2: Find all users who reviewed these hotels
            cursor.execute("""
                SELECT DISTINCT r.author->>'username'
                FROM hotelsapp_review r
                WHERE r.hotel_id IN %s
                  AND r.author->>'username' != %s
            """, [tuple(reviewed_hotel_ids), user.username])
            similar_users = cursor.fetchall()

        if similar_users:
            similar_usernames = [row[0] for row in similar_users]

            # Step 3: Find all hotels reviewed by these users with at least 3.5 rating
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT h.id, h.name, h.address->>'locality' as locality, h.hotel_class, 
                           AVG(CAST(r.ratings->>'overall' AS NUMERIC)) as avg_rating, 
                           COUNT(r.id) as review_count
                    FROM hotelsapp_hotel h
                    JOIN hotelsapp_review r ON h.id = r.hotel_id
                    WHERE CAST(r.ratings->>'overall' AS NUMERIC) >= 3.5
                      AND r.author->>'username' IN %s
                      AND h.id NOT IN (
                        SELECT hotel_id 
                        FROM hotelsapp_review 
                        WHERE author->>'username' = %s
                      )
                    GROUP BY h.id
                    HAVING COUNT(r.id) >= 20
                    ORDER BY avg_rating DESC
                    LIMIT 10
                """, [tuple(similar_usernames), user.username])
                rows = cursor.fetchall()

            recommended_hotels = [
                {'id': row[0], 'name': row[1], 'locality': row[2], 'hotel_class': row[3], 'avg_rating': row[4], 'review_count': row[5]}
                for row in rows
            ]
        else:
            recommended_hotels = []
    else:
        recommended_hotels = []

    if len(recommended_hotels) < 10:
        additional_needed = 10 - len(recommended_hotels)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT h.id, h.name, h.address->>'locality' as locality, h.hotel_class, 
                       AVG(CAST(r.ratings->>'overall' AS NUMERIC)) as avg_rating, 
                       COUNT(r.id) as review_count
                FROM hotelsapp_hotel h
                JOIN hotelsapp_review r ON h.id = r.hotel_id
                WHERE CAST(r.ratings->>'overall' AS NUMERIC) >= 3.5
                  AND h.id NOT IN (
                    SELECT hotel_id 
                    FROM hotelsapp_review 
                    WHERE author->>'username' = %s
                  )
                GROUP BY h.id
                HAVING COUNT(r.id) >= 20
                ORDER BY avg_rating DESC
                LIMIT %s
            """, [user.username, additional_needed])
            additional_rows = cursor.fetchall()

        additional_hotels = [
            {'id': row[0], 'name': row[1], 'locality': row[2], 'hotel_class': row[3], 'avg_rating': row[4], 'review_count': row[5]}
            for row in additional_rows
        ]
        recommended_hotels.extend(additional_hotels[:additional_needed])

    return recommended_hotels


def get_filtered_hotels(min_reviews, locality, min_class, max_class, sort_by):
    where_filters = []
    having_filters = []
    params = []

    if locality:
        where_filters.append("h.address->>'locality' ILIKE %s")
        params.append(f'%{locality}%')

    if min_class is not None and max_class is not None:
        where_filters.append('h.hotel_class BETWEEN %s AND %s')
        params.extend([min_class, max_class])
    elif min_class is not None:
        where_filters.append('h.hotel_class >= %s')
        params.append(min_class)
    elif max_class is not None:
        where_filters.append('h.hotel_class <= %s')
        params.append(max_class)

    query = """
        SELECT h.id, h.name, h.address->>'locality' as locality, h.hotel_class, 
               AVG(CAST(r.ratings->>'overall' AS NUMERIC)) as avg_rating, COUNT(r.id) as review_count
        FROM hotelsapp_hotel h
        JOIN hotelsapp_review r ON h.id = r.hotel_id
    """

    if where_filters:
        query += ' WHERE ' + ' AND '.join(where_filters)

    query += ' GROUP BY h.id, h.name, h.address, h.hotel_class'

    if min_reviews is not None:
        having_filters.append('COUNT(r.id) >= %s')
        params.append(min_reviews)

    if having_filters:
        query += ' HAVING ' + ' AND '.join(having_filters)

    if sort_by == 'top_rated_asc':
        query += ' ORDER BY avg_rating ASC'
    elif sort_by == 'top_rated_desc':
        query += ' ORDER BY avg_rating DESC'
    else:
        query += ' ORDER BY h.id'

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()

    return [{'id': row[0], 'name': row[1], 'locality': row[2], 'hotel_class': row[3], 'avg_rating': row[4], 'review_count': row[5]} for row in rows]


@login_required
def hotels(request):
    user = request.user

    # Fetch recommended hotels
    recommended_hotels = get_recommended_hotels(user)

    # Fetch filtered hotels
    min_reviews = request.GET.get('min_reviews')
    locality = request.GET.get('locality') or ''  # Default to empty string if None
    min_class = request.GET.get('min_class')
    max_class = request.GET.get('max_class')
    sort_by = request.GET.get('sort_by')

    try:
        min_reviews = int(min_reviews) if min_reviews else None
    except ValueError:
        min_reviews = None

    try:
        min_class = float(min_class) if min_class else None
        max_class = float(max_class) if max_class else None
    except ValueError:
        min_class = None
        max_class = None

    filtered_hotels = get_filtered_hotels(min_reviews, locality, min_class, max_class, sort_by)

    # Implementing Pagination
    paginator = Paginator(filtered_hotels, 30)  # Show 30 hotels per page.
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'recommended_hotels': recommended_hotels,
        'page_obj': page_obj,
        'min_reviews': min_reviews,
        'locality': locality,
        'min_class': min_class,
        'max_class': max_class,
        'sort_by': sort_by,
    }

    return render(request, 'hotelsapp/hotels.html', context)


def get_lat_lng(address):
    geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={settings.GOOGLE_MAPS_API_KEY}"
    response = requests.get(geocode_url)
    if response.status_code == 200:
        results = response.json().get('results')
        if results:
            location = results[0].get('geometry').get('location')
            return location.get('lat'), location.get('lng')
    return None, None

@login_required
def hotel_detail(request, hotel_id):
    hotel = get_object_or_404(Hotel, pk=hotel_id)
    reviews = Review.objects.filter(hotel=hotel).order_by('-date')
    overall_rating = HotelOverallRating.objects.get(offering_id=hotel.id)
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(reviews, 5)  

    try:
        reviews = paginator.page(page)
    except PageNotAnInteger:
        reviews = paginator.page(1)
    except EmptyPage:
        reviews = paginator.page(paginator.num_pages)
    
    address = f"{hotel.name}, {hotel.address['street-address']}, {hotel.address['locality']}, {hotel.address['region']} {hotel.address['postal-code']}"
    lat, lng = get_lat_lng(address)
    google_maps_url = f"https://www.google.com/maps/search/?api=1&query={address}"

    if request.method == 'POST':
        ratings = {
            'service': request.POST['service'],
            'cleanliness': request.POST['cleanliness'],
            'overall': request.POST['overall'],
            'value': request.POST['value'],
            'location': request.POST['location'],
            'sleep_quality': request.POST['sleep_quality'],
            'rooms': request.POST['rooms'],
        }
        new_review = Review(
            hotel=hotel,
            ratings=ratings,
            title=request.POST['title'],
            text=request.POST['text'],
            author={'username': request.user.username},
            date_stayed=request.POST['date_stayed'],
            offering_id=hotel.id,
            num_helpful_votes=0,
            date=timezone.now(),
            via_mobile=False,
        )
        new_review.save()

        # Update overall rating
        overall_rating.num_reviews += 1
        overall_rating.average_overall_rating = (overall_rating.average_overall_rating * (overall_rating.num_reviews - 1) + float(ratings['overall'])) / overall_rating.num_reviews
        overall_rating.save()

        return redirect('hotel_detail', hotel_id=hotel_id)

    context = {
        'hotel': hotel,
        'reviews': reviews,
        'overall_rating': overall_rating,
        'lat': lat,
        'lng': lng,
        'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
        'google_maps_url': google_maps_url
    }
    return render(request, 'hotelsapp/hotel_detail.html', context)

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('hotels')
    else:
        form = AuthenticationForm()
    return render(request, 'hotelsapp/login.html', {'form': form})

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('hotels')
    else:
        form = UserCreationForm()
    return render(request, 'hotelsapp/register.html', {'form': form})

@login_required
def account_details_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('account_details')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'hotelsapp/account_details.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')
